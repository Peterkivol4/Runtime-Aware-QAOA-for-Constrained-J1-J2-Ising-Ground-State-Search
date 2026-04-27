from __future__ import annotations

from dataclasses import dataclass
from math import comb
from typing import Any

import numpy as np

from .config import ConstraintPenaltyState, MeasurementOutcome, RunDeck, TailBatch
from .optimization import fourier_to_physical
from .problem import IsingSpinProblem
from ionmesh_runtime.interfaces import QuantumRunner
from ionmesh_runtime._native.fastpath import distribution_stats as _native_distribution_stats
from ionmesh_runtime._native.fastpath import native_enabled as native_fastpath_enabled
from ionmesh_runtime._native.fastpath import weighted_cvar as _native_weighted_cvar
from .runtime_support import RuntimeSamplerFactory, RuntimeSessionManager, runtime_status
from .optional_deps import load_qiskit_aer, load_qiskit_core


def _qiskit_core_tools() -> dict[str, Any] | None:
    try:
        return load_qiskit_core()
    except Exception:
        return None


def _qiskit_aer_tools() -> dict[str, Any] | None:
    try:
        return load_qiskit_aer()
    except Exception:
        return None


@dataclass
class RunnerMetadata:
    backend: str
    runtime_ready: bool
    objective_primitive: str
    measurement_primitive: str
    transpilation_metadata: dict[str, Any]


class ReadoutMitigator:
    def __init__(self, n_qubits: int, p10: float, p01: float):
        self.n_qubits = n_qubits
        confusion = np.array([[1.0 - p10, p01], [p10, 1.0 - p01]], dtype=float)
        self.inv_confusion = np.linalg.inv(confusion)

    def mitigate(self, counts: dict[str, float]) -> dict[str, float]:
        total = float(sum(counts.values()))
        if total <= 0.0:
            return {}
        vector = np.zeros(2**self.n_qubits, dtype=float)
        for bitstring, value in counts.items():
            vector[int(bitstring, 2)] = float(value) / total
        for qubit in range(self.n_qubits):
            vector = vector.reshape(2 ** (self.n_qubits - 1 - qubit), 2, 2**qubit)
            vector = np.einsum("ij,kjl->kil", self.inv_confusion, vector)
            vector = vector.reshape(-1)
        vector = np.clip(vector, 0.0, None)
        norm = float(vector.sum())
        if norm > 0.0:
            vector /= norm
        return {
            format(index, f"0{self.n_qubits}b"): prob * total
            for index, prob in enumerate(vector)
            if prob > 1e-9
        }


class SpinMeasurementEvaluator:
    def __init__(self, cfg: RunDeck, problem: IsingSpinProblem):
        self.cfg = cfg
        self.problem = problem
        self.bitstrings = list(problem.all_bitstrings())
        self.bit_to_index = {bitstring: idx for idx, bitstring in enumerate(self.bitstrings)}
        self.bit_arrays = np.array([problem.bitstring_to_array(bitstring) for bitstring in self.bitstrings], dtype=float)
        self.hamming = self.bit_arrays.sum(axis=1)
        self.valid_mask = self.hamming == float(problem.budget)
        self.invalid_mask = ~self.valid_mask
        self.violations = np.abs(self.hamming - float(problem.budget))
        self.base_energies = np.array([problem.evaluate_energy(bitstring) for bitstring in self.bitstrings], dtype=float)
        self.remapped_bitstrings = [problem.remap_to_valid(bitstring) for bitstring in self.bitstrings]
        self.remapped_energies = np.array([problem.evaluate_energy(bitstring) for bitstring in self.remapped_bitstrings], dtype=float)
        self._observable_cache: dict[tuple[str, float, float], Any] = {}
        self.success_mask = self.valid_mask & ((self.base_energies - self.problem.exact_feasible_energy) <= self.cfg.epsilon_success + 1e-12)

    @staticmethod
    def _weighted_cvar(energies: np.ndarray, weights: np.ndarray, alpha: float) -> tuple[float, float, float]:
        return _native_weighted_cvar(energies, weights, alpha)

    def _penalty_terms(self, penalty_state: ConstraintPenaltyState | None) -> tuple[float, float]:
        if self.cfg.constraint_handling != "penalty":
            return 0.0, 0.0
        if penalty_state is None:
            return 0.0, float(self.cfg.penalty_strength)
        return float(penalty_state.linear_strength), float(penalty_state.quadratic_strength)

    def logit_energies(self, penalty_state: ConstraintPenaltyState | None) -> np.ndarray:
        linear, quadratic = self._penalty_terms(penalty_state)
        if linear == 0.0 and quadratic == 0.0:
            return self.base_energies
        penalties = self.invalid_mask.astype(float) * (linear * self.violations + quadratic * (self.violations**2))
        return self.base_energies + penalties

    def objective_energies(self, penalty_state: ConstraintPenaltyState | None) -> np.ndarray:
        if self.cfg.constraint_handling == "remap":
            return self.remapped_energies
        return self.logit_energies(penalty_state)

    def counts_to_vector(self, counts: dict[str, float]) -> np.ndarray:
        vector = np.zeros(len(self.bitstrings), dtype=float)
        for bitstring, value in counts.items():
            index = self.bit_to_index.get(bitstring)
            if index is not None:
                vector[index] = float(value)
        return vector

    def evaluate_counts(self, counts: dict[str, float], penalty_state: ConstraintPenaltyState | None, shots_used: int, backend: str) -> TailBatch:
        vector = self.counts_to_vector(counts)
        total_weight = float(np.sum(vector))
        if total_weight <= 0.0:
            return TailBatch(cvar=1e9, valid_ratio=0.0, variance=1.0, feasible_best=1e9, raw_best=1e9, total_shots=int(shots_used), backend=backend)
        observed = np.flatnonzero(vector > 0.0)
        objective = self.objective_energies(penalty_state)[observed]
        weights = vector[observed]
        cvar_value, variance, cvar_best = self._weighted_cvar(objective, weights, self.cfg.cvar_alpha)
        raw_best, feasible_best_raw, valid_weight, _, total_weight = _native_distribution_stats(self.base_energies, vector, self.valid_mask, self.success_mask)
        feasible_best = float(cvar_best) if feasible_best_raw >= 1e8 else float(feasible_best_raw)
        return TailBatch(
            cvar=float(cvar_value),
            valid_ratio=float(valid_weight / max(total_weight, 1e-12)),
            variance=float(variance),
            feasible_best=float(feasible_best),
            raw_best=float(raw_best),
            total_shots=int(shots_used),
            backend=backend,
        )

    def measurement_from_counts(self, counts: dict[str, float], penalty_state: ConstraintPenaltyState | None, shots_used: int, backend: str) -> MeasurementOutcome:
        if not counts:
            return MeasurementOutcome({}, "", 0.0, 1e9, 1e9, int(shots_used), backend, success_probability=0.0)
        batch = self.evaluate_counts(counts, penalty_state, shots_used, backend)
        best_bitstring = max(counts.items(), key=lambda item: item[1])[0]
        vector = self.counts_to_vector(counts)
        _, _, _, success_weight, total_weight = _native_distribution_stats(self.base_energies, vector, self.valid_mask, self.success_mask)
        success_probability = 0.0 if total_weight <= 0.0 else float(success_weight / total_weight)
        return MeasurementOutcome(
            counts=counts,
            best_bitstring=best_bitstring,
            valid_ratio=batch.valid_ratio,
            feasible_best=batch.feasible_best,
            raw_best=batch.raw_best,
            total_shots=int(shots_used),
            backend=backend,
            success_probability=success_probability,
        )

    def diagonal_observable(self, penalty_state: ConstraintPenaltyState | None) -> Any:
        tools = _qiskit_core_tools()
        if tools is None:  # pragma: no cover - optional dependency
            raise ImportError("qiskit.quantum_info is required to build a runtime observable.")
        Operator = tools["Operator"]
        SparsePauliOp = tools["SparsePauliOp"]
        linear, quadratic = self._penalty_terms(penalty_state)
        key = (self.cfg.constraint_handling, round(linear, 12), round(quadratic, 12))
        if key not in self._observable_cache:
            diagonal = np.diag(self.objective_energies(penalty_state))
            self._observable_cache[key] = SparsePauliOp.from_operator(Operator(diagonal))
        return self._observable_cache[key]


class NoiseModelFactory:
    @staticmethod
    def build(cfg: RunDeck) -> Any:  # pragma: no cover - only used with qiskit installed
        tools = _qiskit_aer_tools()
        if tools is None:
            raise ImportError("qiskit-aer is not installed.")
        NoiseModel = tools["NoiseModel"]
        thermal_relaxation_error = tools["thermal_relaxation_error"]
        depolarizing_error = tools["depolarizing_error"]
        ReadoutError = tools["ReadoutError"]
        noise_model = NoiseModel()
        one_qubit_thermal = thermal_relaxation_error(cfg.t1_time, cfg.t2_time, cfg.gate_time)
        one_qubit_depol = depolarizing_error(cfg.depol_error, 1)
        one_qubit_error = one_qubit_depol.compose(one_qubit_thermal)
        noise_model.add_all_qubit_quantum_error(one_qubit_error, ["rz", "x", "sx"])
        two_qubit_depol = depolarizing_error(10.0 * cfg.depol_error, 2)
        two_qubit_thermal = one_qubit_thermal.tensor(one_qubit_thermal)
        noise_model.add_all_qubit_quantum_error(two_qubit_depol.compose(two_qubit_thermal), ["rxx", "ryy", "cx"])
        readout = ReadoutError([[1.0 - cfg.readout_p10, cfg.readout_p10], [cfg.readout_p01, 1.0 - cfg.readout_p01]])
        noise_model.add_all_qubit_readout_error(readout)
        return noise_model


def default_penalty_state(cfg: RunDeck) -> ConstraintPenaltyState:
    return ConstraintPenaltyState(
        linear_strength=0.0,
        quadratic_strength=float(cfg.penalty_strength),
        schedule=cfg.penalty_schedule,
        iteration=0,
        epoch=0,
    )


def apply_calibration_snapshot(cfg: RunDeck) -> RunDeck:
    if not cfg.runtime_calibration_snapshot:
        return cfg
    try:
        snapshot = RuntimeSamplerFactory.load_calibration_snapshot(cfg.runtime_calibration_snapshot)
    except Exception:
        return cfg
    profile = RuntimeSamplerFactory.noise_profile_from_snapshot(snapshot)
    return cfg.copy_with(**profile)


def _physical_params(cfg: RunDeck, params: np.ndarray) -> np.ndarray:
    if cfg.parameterization == "fourier":
        return fourier_to_physical(params, cfg.depth, cfg.fourier_modes)
    return np.asarray(params, dtype=float)


def _prepare_dicke_state(n: int, k: int, circuit: Any) -> None:
    tools = _qiskit_core_tools()
    if tools is None:
        raise ImportError("qiskit is required to prepare Dicke states.")
    if k <= 0:
        return
    if k >= n:
        for qubit in range(n):
            circuit.x(qubit)
        return
    amplitudes = np.zeros(2**n, dtype=complex)
    target_prob = 1.0 / comb(n, k)
    for basis_index in range(2**n):
        if basis_index.bit_count() == k:
            amplitudes[basis_index] = np.sqrt(target_prob)
    state_preparation = tools["StatePreparation"](amplitudes)
    circuit.append(state_preparation, list(range(n)))


def _build_parametric_qaoa_circuit(cfg: RunDeck, gamma: Any, beta: Any, *, measure: bool) -> Any:
    tools = _qiskit_core_tools()
    if tools is None:
        raise ImportError("qiskit is required to build quantum circuits.")
    circuit = tools["QuantumCircuit"](cfg.n_spins)
    _prepare_dicke_state(cfg.n_spins, cfg.budget, circuit)
    for layer in range(cfg.depth):
        for qubit in range(cfg.n_spins):
            circuit.rz(gamma[layer], qubit)
        for qubit in range(cfg.n_spins - 1):
            circuit.rxx(beta[layer], qubit, qubit + 1)
            circuit.ryy(beta[layer], qubit, qubit + 1)
    if measure:
        circuit.measure_all()
    return circuit


def _fold_global_circuit(circuit: Any, repeats: int) -> Any:
    if repeats == 1:
        return circuit
    if not hasattr(circuit, "remove_final_measurements"):
        raise ValueError("Global folding requires a qiskit circuit.")
    core = circuit.remove_final_measurements(inplace=False)
    folded = core.copy()
    for _ in range((repeats - 1) // 2):
        folded.compose(core.inverse(), inplace=True)
        folded.compose(core, inplace=True)
    folded.measure_all()
    return folded


def _diagonal_observable(problem: IsingSpinProblem, cfg: RunDeck, penalty_state: ConstraintPenaltyState | None) -> Any:
    evaluator = SpinMeasurementEvaluator(cfg, problem)
    return evaluator.diagonal_observable(penalty_state)


def _observable_for_isa(observable: Any, isa_circuit: Any) -> Any:
    apply_layout = getattr(observable, "apply_layout", None)
    if not callable(apply_layout):
        return observable
    return apply_layout(getattr(isa_circuit, "layout", None), num_qubits=getattr(isa_circuit, "num_qubits", None))


class ProxyQuantumRunner(QuantumRunner):
    def __init__(self, cfg: RunDeck, problem: IsingSpinProblem):
        self.cfg = cfg
        self.problem = problem
        self.rng = np.random.default_rng(cfg.seed)
        self.mitigator = ReadoutMitigator(cfg.n_spins, cfg.readout_p10, cfg.readout_p01)
        self.evaluator = SpinMeasurementEvaluator(cfg, problem)
        self.bitstrings = self.evaluator.bitstrings
        self.bit_arrays = self.evaluator.bit_arrays
        self.hamming = self.evaluator.hamming
        self.objective_calls = 0
        self.sampler_calls = 0
        self.metadata = RunnerMetadata(
            backend="proxy",
            runtime_ready=runtime_status().available,
            objective_primitive="proxy_expectation",
            measurement_primitive="proxy_sampler",
            transpilation_metadata={"backend_name": "proxy", "isa_simulated": False},
        )

    def _logits(self, params: np.ndarray, noise_scale: float, penalty_state: ConstraintPenaltyState | None) -> np.ndarray:
        physical = _physical_params(self.cfg, params)
        gamma = physical[: self.cfg.depth]
        beta = physical[self.cfg.depth :]
        z = 2.0 * self.bit_arrays - 1.0
        field_profile = np.sin(np.arange(1, self.problem.n + 1) * 0.73 + np.sum(gamma))
        mixer_profile = np.cos(np.arange(1, self.problem.n) * 0.41 + np.sum(beta))
        field_term = z @ field_profile
        pair_term = np.sum(z[:, :-1] * z[:, 1:] * mixer_profile, axis=1)
        energies = self.evaluator.logit_energies(penalty_state)
        budget_penalty = np.abs(self.hamming - self.problem.budget)
        concentration = 1.0 + 0.35 * self.cfg.depth + 0.15 * np.linalg.norm(physical) / max(1, len(physical))
        leakage = noise_scale * (1.0 + 0.2 * self.cfg.depth)
        penalty_boost = 0.0 if penalty_state is None else 0.015 * penalty_state.quadratic_strength * budget_penalty
        logits = -concentration * energies + 0.12 * field_term - 0.08 * pair_term - leakage * budget_penalty - penalty_boost
        return logits

    def _counts_from_logits(self, logits: np.ndarray, noise_scale: float, shots: int) -> dict[str, float]:
        logits = logits - np.max(logits)
        probs = np.exp(logits)
        probs /= np.sum(probs)
        if self.cfg.use_noise:
            effective_noise = min(0.45, noise_scale)
            probs = (1.0 - effective_noise) * probs + effective_noise * np.full_like(probs, 1.0 / len(probs))
        draws = self.rng.multinomial(shots, probs)
        counts = {bitstring: float(draws[idx]) for idx, bitstring in enumerate(self.bitstrings) if draws[idx] > 0}
        if self.cfg.use_noise and self.cfg.use_readout_mitigation:
            counts = self.mitigator.mitigate(counts)
        return counts

    def _evaluate_counts(self, counts: dict[str, float], penalty_state: ConstraintPenaltyState | None, shots_used: int) -> TailBatch:
        return self.evaluator.evaluate_counts(counts, penalty_state, shots_used, self.metadata.backend)

    def _measurement_from_counts(self, counts: dict[str, float], penalty_state: ConstraintPenaltyState | None, shots_used: int) -> MeasurementOutcome:
        return self.evaluator.measurement_from_counts(counts, penalty_state, shots_used, self.metadata.backend)

    def _run_once(self, params: np.ndarray, *, noise_multiplier: float, penalty_state: ConstraintPenaltyState | None, shots: int) -> TailBatch:
        logits = self._logits(params, noise_scale=self.cfg.noise_level * noise_multiplier, penalty_state=penalty_state)
        counts = self._counts_from_logits(logits, noise_scale=self.cfg.noise_level * noise_multiplier, shots=shots)
        return self._evaluate_counts(counts, penalty_state, shots)

    def evaluate_objective(self, params: np.ndarray, penalty_state: ConstraintPenaltyState | None = None, *, shots: int | None = None) -> TailBatch:
        penalty_state = penalty_state or default_penalty_state(self.cfg)
        self.objective_calls += 1
        used_shots = int(shots or self.cfg.dynamic_shots)
        base = self._run_once(params, noise_multiplier=1.0, penalty_state=penalty_state, shots=used_shots)
        if not self.cfg.use_zne:
            return base
        folded_3 = self._run_once(params, noise_multiplier=3.0, penalty_state=penalty_state, shots=used_shots)
        folded_5 = self._run_once(params, noise_multiplier=5.0, penalty_state=penalty_state, shots=used_shots)
        zne_cvar = 1.875 * base.cvar - 1.25 * folded_3.cvar + 0.375 * folded_5.cvar
        zne_variance = (1.875**2) * base.variance + (1.25**2) * folded_3.variance + (0.375**2) * folded_5.variance
        return TailBatch(
            cvar=float(zne_cvar),
            valid_ratio=base.valid_ratio,
            variance=float(max(1e-12, zne_variance)),
            feasible_best=base.feasible_best,
            raw_best=base.raw_best,
            total_shots=base.total_shots + folded_3.total_shots + folded_5.total_shots,
            backend=self.metadata.backend,
        )

    def sample_final_readout(
        self,
        params: np.ndarray,
        penalty_state: ConstraintPenaltyState | None = None,
        *,
        shots: int | None = None,
    ) -> MeasurementOutcome:
        penalty_state = penalty_state or default_penalty_state(self.cfg)
        self.sampler_calls += 1
        used_shots = int(shots or self.cfg.dynamic_shots)
        logits = self._logits(params, noise_scale=self.cfg.noise_level, penalty_state=penalty_state)
        counts = self._counts_from_logits(logits, noise_scale=self.cfg.noise_level, shots=used_shots)
        return self._measurement_from_counts(counts, penalty_state, used_shots)

    def execution_metadata(self) -> dict[str, Any]:
        payload = dict(self.metadata.transpilation_metadata)
        payload.update({"objective_calls": self.objective_calls, "sampler_calls": self.sampler_calls})
        return payload

    def run(self, params: np.ndarray) -> TailBatch:
        return self.evaluate_objective(params)


class AerQuantumRunner(QuantumRunner):  # pragma: no cover - optional dependency
    def __init__(self, cfg: RunDeck, problem: IsingSpinProblem):
        core = _qiskit_core_tools()
        aer_tools = _qiskit_aer_tools()
        if core is None or aer_tools is None:
            raise ImportError("qiskit and qiskit-aer are required for Aer execution.")
        ParameterVector = core["ParameterVector"]
        BackendSamplerV2 = core["BackendSamplerV2"]
        generate_preset_pass_manager = core["generate_preset_pass_manager"]
        AerSimulator = aer_tools["AerSimulator"]
        self.cfg = cfg
        self.problem = problem
        self.evaluator = SpinMeasurementEvaluator(cfg, problem)
        self.mitigator = ReadoutMitigator(cfg.n_spins, cfg.readout_p10, cfg.readout_p01)
        self.gamma = ParameterVector("gamma", cfg.depth)
        self.beta = ParameterVector("beta", cfg.depth)
        self.measured_circuit = _build_parametric_qaoa_circuit(cfg, self.gamma, self.beta, measure=True)
        self.folded_measured_3 = _fold_global_circuit(self.measured_circuit, 3) if cfg.use_zne else None
        self.folded_measured_5 = _fold_global_circuit(self.measured_circuit, 5) if cfg.use_zne else None
        self.backend = AerSimulator(noise_model=NoiseModelFactory.build(cfg) if cfg.use_noise else None, seed_simulator=cfg.seed)
        self.objective_calls = 0
        self.sampler_calls = 0
        pass_manager = generate_preset_pass_manager(optimization_level=1, backend=self.backend)
        self.isa_circuit = pass_manager.run(self.measured_circuit)
        self.isa_folded_3 = pass_manager.run(self.folded_measured_3) if self.folded_measured_3 is not None else None
        self.isa_folded_5 = pass_manager.run(self.folded_measured_5) if self.folded_measured_5 is not None else None
        self.sampler = BackendSamplerV2(backend=self.backend)
        self.metadata = RunnerMetadata(
            backend="aer",
            runtime_ready=runtime_status().available,
            objective_primitive="aer_sampler_proxy_objective",
            measurement_primitive="aer_sampler",
            transpilation_metadata=RuntimeSamplerFactory.transpilation_metadata(self.backend, self.isa_circuit),
        )

    def _binding_map(self, physical: np.ndarray) -> dict[Any, float]:
        binding = {self.gamma[idx]: float(physical[idx]) for idx in range(self.cfg.depth)}
        binding.update({self.beta[idx]: float(physical[self.cfg.depth + idx]) for idx in range(self.cfg.depth)})
        return binding

    @staticmethod
    def _extract_counts(result: Any) -> dict[str, float]:
        data = result.data
        meas = getattr(data, "meas", None)
        if meas is None:
            meas = data["meas"]
        return dict(meas.get_counts())

    def _execute(self, circuit: Any, physical: np.ndarray, penalty_state: ConstraintPenaltyState | None, shots: int) -> TailBatch:
        self.sampler_calls += 1
        bound = circuit.assign_parameters(self._binding_map(physical), inplace=False)
        result = self.sampler.run([bound], shots=shots).result()[0]
        counts = self._extract_counts(result)
        if self.cfg.use_noise and self.cfg.use_readout_mitigation:
            counts = self.mitigator.mitigate(counts)
        return self.evaluator.evaluate_counts(counts, penalty_state, shots, self.metadata.backend)

    def evaluate_objective(self, params: np.ndarray, penalty_state: ConstraintPenaltyState | None = None, *, shots: int | None = None) -> TailBatch:
        penalty_state = penalty_state or default_penalty_state(self.cfg)
        self.objective_calls += 1
        physical = _physical_params(self.cfg, params)
        used_shots = int(shots or self.cfg.dynamic_shots)
        base = self._execute(self.isa_circuit, physical, penalty_state, used_shots)
        if not self.cfg.use_zne or self.isa_folded_3 is None or self.isa_folded_5 is None:
            return base
        est3 = self._execute(self.isa_folded_3, physical, penalty_state, used_shots)
        est5 = self._execute(self.isa_folded_5, physical, penalty_state, used_shots)
        return TailBatch(
            cvar=float(1.875 * base.cvar - 1.25 * est3.cvar + 0.375 * est5.cvar),
            valid_ratio=base.valid_ratio,
            variance=float(max(1e-12, (1.875**2) * base.variance + (1.25**2) * est3.variance + (0.375**2) * est5.variance)),
            feasible_best=base.feasible_best,
            raw_best=base.raw_best,
            total_shots=base.total_shots + est3.total_shots + est5.total_shots,
            backend=self.metadata.backend,
        )

    def sample_final_readout(self, params: np.ndarray, penalty_state: ConstraintPenaltyState | None = None, *, shots: int | None = None) -> MeasurementOutcome:
        penalty_state = penalty_state or default_penalty_state(self.cfg)
        self.sampler_calls += 1
        physical = _physical_params(self.cfg, params)
        bound = self.isa_circuit.assign_parameters(self._binding_map(physical), inplace=False)
        used_shots = int(shots or self.cfg.dynamic_shots)
        result = self.sampler.run([bound], shots=used_shots).result()[0]
        counts = self._extract_counts(result)
        if self.cfg.use_noise and self.cfg.use_readout_mitigation:
            counts = self.mitigator.mitigate(counts)
        return self.evaluator.measurement_from_counts(counts, penalty_state, used_shots, self.metadata.backend)

    def execution_metadata(self) -> dict[str, Any]:
        payload = dict(self.metadata.transpilation_metadata)
        payload.update({"objective_calls": self.objective_calls, "sampler_calls": self.sampler_calls})
        return payload

    def run(self, params: np.ndarray) -> TailBatch:
        return self.evaluate_objective(params)


class RuntimeQuantumRunner(QuantumRunner):
    def __init__(self, cfg: RunDeck, problem: IsingSpinProblem):
        status = runtime_status()
        if not status.available:  # pragma: no cover - optional dependency
            raise ImportError(status.message)
        core = _qiskit_core_tools()
        if core is None:
            raise ImportError("qiskit is required for Runtime execution.")
        ParameterVector = core["ParameterVector"]
        self.cfg = cfg
        self.problem = problem
        self.evaluator = SpinMeasurementEvaluator(cfg, problem)
        self.mitigator = ReadoutMitigator(cfg.n_spins, cfg.readout_p10, cfg.readout_p01)
        self.gamma = ParameterVector("gamma", cfg.depth)
        self.beta = ParameterVector("beta", cfg.depth)
        self.ansatz_circuit = _build_parametric_qaoa_circuit(cfg, self.gamma, self.beta, measure=False)
        self.measured_circuit = _build_parametric_qaoa_circuit(cfg, self.gamma, self.beta, measure=True)
        self.service = RuntimeSamplerFactory.create_service(cfg, strict=True)
        self.backend = RuntimeSamplerFactory.select_backend(self.service, cfg.runtime_backend)
        self.isa_ansatz = RuntimeSamplerFactory.make_isa_circuit(self.ansatz_circuit, self.backend)
        self.isa_measured = RuntimeSamplerFactory.make_isa_circuit(self.measured_circuit, self.backend)
        self.session_manager = RuntimeSessionManager(cfg, self.backend)
        self.estimator = self.session_manager.estimator
        self.sampler = self.session_manager.sampler
        self.context = self.session_manager.context
        self.eval_counter = 0
        self.estimator_calls = 0
        self.sampler_calls = 0
        self.metadata = RunnerMetadata(
            backend="runtime_v2",
            runtime_ready=True,
            objective_primitive="estimator_v2",
            measurement_primitive="sampler_v2",
            transpilation_metadata=RuntimeSamplerFactory.transpilation_metadata(self.backend, self.isa_measured),
        )

    @staticmethod
    def _runtime_values(physical: np.ndarray) -> list[float]:
        return [float(v) for v in physical]

    @staticmethod
    def _extract_counts(runtime_result: Any) -> dict[str, float]:
        data = runtime_result.data
        meas = getattr(data, "meas", None)
        if meas is None:
            meas = data["meas"]
        return dict(meas.get_counts())

    def _should_probe_sidecar(self) -> bool:
        if not self.cfg.runtime_probe_readout_each_eval:
            return False
        if self.cfg.runtime_probe_policy == "never":
            return False
        if self.cfg.runtime_probe_policy == "local_only":
            return False
        return self.eval_counter % self.cfg.runtime_probe_frequency == 0

    def _sidecar_sampler_probe(self, physical: np.ndarray, penalty_state: ConstraintPenaltyState, shots: int) -> MeasurementOutcome:
        self.sampler_calls += 1
        result = self.session_manager.run_sampler([(self.isa_measured, self._runtime_values(physical), shots)])[0]
        counts = self._extract_counts(result)
        if self.cfg.use_readout_mitigation:
            counts = self.mitigator.mitigate(counts)
        outcome = self.evaluator.measurement_from_counts(counts, penalty_state, shots, self.metadata.backend)
        outcome.backend = self.metadata.backend
        return outcome

    def evaluate_objective(self, params: np.ndarray, penalty_state: ConstraintPenaltyState | None = None, *, shots: int | None = None) -> TailBatch:
        penalty_state = penalty_state or default_penalty_state(self.cfg)
        self.eval_counter += 1
        physical = _physical_params(self.cfg, params)
        observable = _observable_for_isa(self.evaluator.diagonal_observable(penalty_state), self.isa_ansatz)
        self.estimator_calls += 1
        result = self.session_manager.run_estimator([(self.isa_ansatz, observable, self._runtime_values(physical))])[0]
        evs = getattr(result.data, "evs", None)
        if isinstance(evs, (list, tuple, np.ndarray)):
            objective_value = float(np.asarray(evs).reshape(-1)[0])
        else:
            objective_value = float(evs)
        if self._should_probe_sidecar():
            probe = self._sidecar_sampler_probe(physical, penalty_state, min(self.cfg.runtime_probe_shots, self.cfg.dynamic_shots))
            return TailBatch(
                cvar=objective_value,
                valid_ratio=probe.valid_ratio,
                variance=0.0,
                feasible_best=probe.feasible_best,
                raw_best=probe.raw_best,
                total_shots=probe.total_shots,
                backend=self.metadata.backend,
            )
        return TailBatch(
            cvar=objective_value,
            valid_ratio=float("nan"),
            variance=0.0,
            feasible_best=objective_value,
            raw_best=objective_value,
            total_shots=0,
            backend=self.metadata.backend,
        )

    def sample_final_readout(self, params: np.ndarray, penalty_state: ConstraintPenaltyState | None = None, *, shots: int | None = None) -> MeasurementOutcome:
        penalty_state = penalty_state or default_penalty_state(self.cfg)
        self.sampler_calls += 1
        physical = _physical_params(self.cfg, params)
        return self._sidecar_sampler_probe(physical, penalty_state, int(shots or self.cfg.dynamic_shots))

    def execution_metadata(self) -> dict[str, Any]:
        payload = dict(self.metadata.transpilation_metadata)
        payload["runtime_probe_policy"] = self.cfg.runtime_probe_policy
        payload["runtime_probe_frequency"] = self.cfg.runtime_probe_frequency
        payload["estimator_calls"] = self.estimator_calls
        payload["sampler_calls"] = self.sampler_calls
        payload["session_plan"] = self.session_manager.metadata()
        return payload

    def run(self, params: np.ndarray) -> TailBatch:
        return self.evaluate_objective(params)


def build_quantum_runner(cfg: RunDeck, problem: IsingSpinProblem) -> Any:
    effective_cfg = apply_calibration_snapshot(cfg)
    if effective_cfg.runtime_mode == "runtime_v2":
        return RuntimeQuantumRunner(effective_cfg, problem)
    if effective_cfg.runtime_mode == "aer":
        return AerQuantumRunner(effective_cfg, problem)
    if effective_cfg.runtime_mode == "local_proxy":
        return ProxyQuantumRunner(effective_cfg, problem)
    if _qiskit_core_tools() is not None and _qiskit_aer_tools() is not None:
        return AerQuantumRunner(effective_cfg, problem)
    return ProxyQuantumRunner(effective_cfg, problem)

__all__ = [
    'RunnerMetadata',
    'ReadoutMitigator',
    'SpinMeasurementEvaluator',
    'NoiseModelFactory',
    'default_penalty_state',
    'apply_calibration_snapshot',
    '_observable_for_isa',
    '_prepare_dicke_state',
    'ProxyQuantumRunner',
    'AerQuantumRunner',
    'RuntimeQuantumRunner',
    'build_quantum_runner',
]
