from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .optional_deps import load_mannwhitneyu, load_pandas

from .baselines import ClassicalBaselines
from .config import ConstraintPenaltyState, MeasurementOutcome, RunDeck, TailBatch, TrialResult
from .decision import build_decision_report, compute_utility_frontier
from .constants import DEFAULT_BOOTSTRAP, DEFAULT_SMOKE_OVERRIDES
from .governor import ShotBudgetGovernor
from .logging_utils import set_reproducibility, setup_logging
from .optimization import GaussianProcessBayesOptimizer, project_params, spsa_step
from .plotting import (
    plot_approximation_gap_vs_evaluations,
    plot_energy_gap_vs_j2_ratio,
    plot_mitigation_gain_vs_shot_budget,
    plot_performance_profile,
    plot_qaoa_optimizer_sample_efficiency,
    plot_success_probability_vs_noise,
    plot_valid_sector_ratio_vs_spins,
    plot_valid_ratio_vs_depth,
)
from .problem import IsingSpinProblem
from .quantum import build_quantum_runner
from .tracking import RunLedger, json_dumps_clean, physics_label_payload, sanitize_json_payload


QAOA_METHODS = ("bo_fourier", "spsa_fourier", "random_fourier", "bo_direct")


def _with_physics_labels(frame: pd.DataFrame) -> pd.DataFrame:
    labeled = frame.copy()
    if "regime" in labeled.columns and "lattice_type" not in labeled.columns:
        labeled["lattice_type"] = labeled["regime"]
    if "n_assets" in labeled.columns and "n_spins" not in labeled.columns:
        labeled["n_spins"] = labeled["n_assets"]
    if "valid_ratio" in labeled.columns and "valid_sector_ratio" not in labeled.columns:
        labeled["valid_sector_ratio"] = labeled["valid_ratio"]
    return labeled


def _problem_label(row: pd.Series) -> str:
    lattice_type = row.get("lattice_type", row.get("regime"))
    n_spins = row.get("n_spins", row.get("n_assets"))
    return (
        f"{row['seed']}|{lattice_type}|{n_spins}|{row['budget']}|{row['depth']}|"
        f"{row['noise_level']}|{row['shot_budget']}|{row.get('j2_ratio', 'na')}|{row.get('disorder_strength', 'na')}"
    )


def _physics_rows(frame: pd.DataFrame, *, limit: int = 1) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    rows = frame.head(limit).to_dict(orient="records")
    return [physics_label_payload(row) for row in rows]


@dataclass
class PenaltyController:
    cfg: RunDeck
    total_steps: int
    current_quadratic: float
    current_linear: float = 0.0
    epoch_valid_ratios: list[float] | None = None

    def __post_init__(self) -> None:
        if self.epoch_valid_ratios is None:
            self.epoch_valid_ratios = []

    @classmethod
    def create(cls, cfg: RunDeck, total_steps: int) -> "PenaltyController":
        start = cfg.penalty_strength if cfg.penalty_schedule == "static" else max(1e-6, 0.25 * cfg.penalty_strength)
        return cls(cfg=cfg, total_steps=max(1, total_steps), current_quadratic=float(start), current_linear=0.0)

    def state_dict(self) -> dict[str, Any]:
        return {
            "current_quadratic": float(self.current_quadratic),
            "current_linear": float(self.current_linear),
            "epoch_valid_ratios": [float(v) for v in (self.epoch_valid_ratios or [])],
        }

    def load_state_dict(self, payload: dict[str, Any] | None) -> None:
        if not payload:
            return
        self.current_quadratic = float(payload.get("current_quadratic", self.current_quadratic))
        self.current_linear = float(payload.get("current_linear", self.current_linear))
        self.epoch_valid_ratios = [float(v) for v in payload.get("epoch_valid_ratios", [])]

    def epoch_for(self, iteration: int) -> int:
        return max(0, (max(1, iteration) - 1) // max(1, self.cfg.penalty_epoch_length))

    def penalty_context(self, penalty_state: ConstraintPenaltyState) -> np.ndarray:
        denom = max(self.cfg.penalty_strength * self.cfg.penalty_max_multiplier, 1e-9)
        linear = penalty_state.linear_strength / denom
        quadratic = penalty_state.quadratic_strength / denom
        epoch = penalty_state.epoch / max(1, math.ceil(self.total_steps / max(1, self.cfg.penalty_epoch_length)))
        return np.array([linear, quadratic, epoch], dtype=float)

    def state(self, iteration: int) -> ConstraintPenaltyState:
        epoch = self.epoch_for(iteration)
        if self.cfg.constraint_handling != "penalty":
            return ConstraintPenaltyState(0.0, 0.0, self.cfg.penalty_schedule, iteration, epoch)
        if self.cfg.penalty_schedule == "static":
            return ConstraintPenaltyState(0.0, float(self.cfg.penalty_strength), "static", iteration, epoch)
        if self.cfg.penalty_schedule == "annealed":
            total_epochs = max(1, math.ceil(self.total_steps / max(1, self.cfg.penalty_epoch_length)))
            warmup_epochs = max(1, int(math.ceil(total_epochs * self.cfg.penalty_warmup_fraction)))
            progress = 0.0 if epoch < warmup_epochs else (epoch - warmup_epochs + 1) / max(1, total_epochs - warmup_epochs)
            multiplier = 0.25 + (self.cfg.penalty_growth_factor - 0.25) * min(1.0, max(0.0, progress))
            return ConstraintPenaltyState(0.0, float(self.cfg.penalty_strength * multiplier), "annealed", iteration, epoch)
        return ConstraintPenaltyState(
            float(self.current_linear),
            float(self.current_quadratic),
            "augmented_lagrangian",
            iteration,
            epoch,
        )

    def observe(self, batch: TailBatch, iteration: int | None = None) -> None:
        if self.cfg.constraint_handling != "penalty":
            return
        if self.cfg.penalty_schedule != "augmented_lagrangian":
            return
        iteration = self.total_steps if iteration is None else iteration
        self.epoch_valid_ratios.append(float(batch.valid_ratio if math.isfinite(batch.valid_ratio) else 0.0))
        is_last_in_epoch = iteration % max(1, self.cfg.penalty_epoch_length) == 0 or iteration == self.total_steps
        if not is_last_in_epoch:
            return
        epoch_valid_ratio = float(np.mean(self.epoch_valid_ratios)) if self.epoch_valid_ratios else 0.0
        self.epoch_valid_ratios.clear()
        violation = max(0.0, 1.0 - epoch_valid_ratio)
        self.current_linear = max(0.0, self.current_linear + self.cfg.alm_dual_lr * violation)
        multiplier = 1.0 + self.cfg.penalty_growth_factor * violation
        capped = self.cfg.penalty_strength * self.cfg.penalty_max_multiplier
        self.current_quadratic = min(capped, max(self.cfg.penalty_strength * 0.25, self.current_quadratic * multiplier))


@dataclass
class OptimizationOutcome:
    record: TrialResult
    best_params: np.ndarray


def _mitigation_label(cfg: RunDeck) -> str:
    tags: list[str] = []
    if cfg.use_readout_mitigation:
        tags.append("readout")
    if cfg.use_zne:
        tags.append("zne")
    if cfg.use_twirling:
        tags.append("twirling")
    if cfg.use_dynamical_decoupling:
        tags.append("dd")
    return "+".join(tags) if tags else "none"


def _parameter_dim(cfg: RunDeck) -> int:
    if cfg.parameterization == "fourier":
        return 2 * cfg.fourier_modes
    return 2 * cfg.depth


def _approximation_ratio(best_energy: float, exact_energy: float) -> float:
    scale = max(abs(float(exact_energy)), 1e-9)
    return float(1.0 + max(0.0, float(best_energy) - float(exact_energy)) / scale)


def _trial_steps(cfg: RunDeck, method: str) -> int:
    if method in {"bo_fourier", "bo_direct"}:
        return cfg.bo_iters
    if method == "random_fourier":
        return cfg.random_search_iters
    return cfg.spsa_iters


def _estimated_total_shots(cfg: RunDeck, method: str) -> int:
    steps = _trial_steps(cfg, method)
    per_eval = cfg.shot_governor_max_shots if cfg.shot_governor_enabled else cfg.dynamic_shots
    if cfg.use_zne:
        per_eval *= 3
    if cfg.runtime_probe_readout_each_eval and cfg.runtime_probe_policy == "always":
        per_eval += min(cfg.runtime_probe_shots, cfg.dynamic_shots)
    final_readout = cfg.dynamic_shots
    return int(steps * per_eval + final_readout)


def _build_runtime_budget_cfg(cfg: RunDeck, method: str) -> RunDeck:
    return cfg.copy_with(runtime_estimated_total_shots=_estimated_total_shots(cfg, method))


def _record_from_trace(
    cfg: RunDeck,
    problem: IsingSpinProblem,
    method: str,
    trace: list[dict[str, float]],
    started_at: float,
    best_params: np.ndarray,
    final_bitstring: str | None,
    transpilation_metadata: dict[str, Any],
    objective_calls: int,
    objective_shots_used: int,
) -> TrialResult:
    best = min(step["best_energy"] for step in trace)
    runtime_seconds = time.time() - started_at
    gap = max(0.0, best - problem.exact_feasible_energy)
    valid_series = [step["valid_ratio"] for step in trace if math.isfinite(step["valid_ratio"])]
    final_valid = valid_series[-1] if valid_series else 0.0
    return TrialResult(
        method=method,
        family="qaoa",
        regime=problem.regime,
        seed=cfg.seed,
        n_assets=problem.n,
        budget=problem.budget,
        depth=cfg.depth,
        noise_level=cfg.noise_level,
        shot_budget=cfg.base_shots,
        parameterization=cfg.parameterization,
        mitigation_label=_mitigation_label(cfg),
        constraint_handling=cfg.constraint_handling,
        best_energy=float(best),
        exact_energy=float(problem.exact_feasible_energy),
        approximation_gap=float(gap),
        approximation_ratio=_approximation_ratio(best, problem.exact_feasible_energy),
        success=gap <= cfg.epsilon_success,
        valid_ratio=float(final_valid),
        measurement_success_probability=0.0,
        runtime_seconds=float(runtime_seconds),
        evaluations=len(trace),
        objective_calls=int(objective_calls),
        total_shots=int(objective_shots_used),
        sampler_calls=0,
        primitive_calls=int(objective_calls),
        final_readout_shots=0,
        optimization_best_energy=float(best),
        final_readout_energy=None,
        final_readout_valid_ratio=None,
        final_readout_raw_best=None,
        final_bitstring=final_bitstring,
        best_params=[float(value) for value in np.asarray(best_params).reshape(-1)],
        transpilation_metadata=transpilation_metadata,
        trace=trace,
        j2_ratio=cfg.j2_ratio,
        disorder_strength=cfg.disorder_strength,
        frustration_index=problem.frustration_index,
        magnetization_m=cfg.magnetization_m,
    )


def _finalize_qaoa_record(
    record: TrialResult,
    problem: IsingSpinProblem,
    cfg: RunDeck,
    final_measurement: MeasurementOutcome,
) -> TrialResult:
    record.final_readout_energy = float(final_measurement.feasible_best)
    record.final_readout_valid_ratio = float(final_measurement.valid_ratio)
    record.final_readout_raw_best = float(final_measurement.raw_best)
    record.final_readout_shots = int(final_measurement.total_shots)
    record.total_shots = int(record.total_shots + final_measurement.total_shots)
    record.sampler_calls = int(record.sampler_calls + 1)
    record.primitive_calls = int(record.objective_calls + record.sampler_calls)
    record.valid_ratio = float(final_measurement.valid_ratio)
    record.measurement_success_probability = float(final_measurement.success_probability)
    record.best_energy = float(min(record.best_energy, final_measurement.feasible_best))
    record.approximation_gap = max(0.0, record.best_energy - problem.exact_feasible_energy)
    record.approximation_ratio = _approximation_ratio(record.best_energy, problem.exact_feasible_energy)
    record.success = record.approximation_gap <= cfg.epsilon_success
    return record


def _checkpoint_payload(
    *,
    method: str,
    cfg: RunDeck,
    evaluation: int,
    trace: list[dict[str, float]],
    best_energy: float,
    best_params: np.ndarray,
    current_params: np.ndarray | None,
    rng: np.random.Generator,
    penalty_controller: PenaltyController,
    optimizer: GaussianProcessBayesOptimizer | None = None,
    extra_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "method": method,
        "cfg_seed": cfg.seed,
        "evaluation": int(evaluation),
        "trace": trace,
        "best_energy": float(best_energy),
        "best_params": np.asarray(best_params, dtype=float).tolist(),
        "current_params": None if current_params is None else np.asarray(current_params, dtype=float).tolist(),
        "rng_state": rng.bit_generator.state,
        "penalty_controller": penalty_controller.state_dict(),
        "optimizer_state": None if optimizer is None else optimizer.state_dict(),
        "extra_state": extra_state or {},
    }


def _restore_checkpoint(
    checkpoint: dict[str, Any] | None,
    *,
    rng: np.random.Generator,
    penalty_controller: PenaltyController,
) -> tuple[int, list[dict[str, float]], float, np.ndarray | None, np.ndarray | None, dict[str, Any], dict[str, Any] | None]:
    if not checkpoint:
        return 1, [], float("inf"), None, None, {}, None
    if checkpoint.get("rng_state") is not None:
        rng.bit_generator.state = checkpoint["rng_state"]
    penalty_controller.load_state_dict(checkpoint.get("penalty_controller"))
    trace = checkpoint.get("trace", [])
    best_params = np.asarray(checkpoint.get("best_params"), dtype=float) if checkpoint.get("best_params") is not None else None
    current_params = np.asarray(checkpoint.get("current_params"), dtype=float) if checkpoint.get("current_params") is not None else None
    start_eval = int(checkpoint.get("evaluation", 0)) + 1
    best_energy = float(checkpoint.get("best_energy", float("inf")))
    extra_state = checkpoint.get("extra_state", {})
    return start_eval, trace, best_energy, best_params, current_params, extra_state, checkpoint.get("optimizer_state")


def _evaluate_qaoa(cfg: RunDeck, problem: IsingSpinProblem, method: str, checkpoint_db_path: str | Path | None = None) -> OptimizationOutcome:
    started_at = time.time()
    working_cfg = cfg if method != "bo_direct" else cfg.copy_with(parameterization="direct")
    working_cfg = _build_runtime_budget_cfg(working_cfg, method)
    runner = build_quantum_runner(working_cfg, problem)
    dim = _parameter_dim(working_cfg)
    rng = np.random.default_rng(working_cfg.seed)
    total_steps = _trial_steps(working_cfg, method)
    penalty_controller = PenaltyController.create(working_cfg, total_steps)
    governor = ShotBudgetGovernor(working_cfg, total_steps)
    run_key = RunLedger.make_run_key(working_cfg, method)
    checkpoint = None
    if checkpoint_db_path is not None and working_cfg.runtime_resume_enabled:
        checkpoint = RunLedger.load_optimizer_checkpoint(checkpoint_db_path, run_key)
    start_eval, trace, best_energy, restored_best_params, restored_current_params, extra_state, optimizer_state = _restore_checkpoint(
        checkpoint,
        rng=rng,
        penalty_controller=penalty_controller,
    )
    if extra_state.get("shot_governor"):
        governor_state = extra_state["shot_governor"]
        governor.cumulative_shots = int(governor_state.get("cumulative_shots", governor.cumulative_shots))
        governor.current_shots = int(governor_state.get("current_shots", governor.current_shots))
        governor.stagnant_steps = int(governor_state.get("stagnant_steps", governor.stagnant_steps))
        governor.last_best_energy = float(governor_state.get("last_best_energy", governor.last_best_energy))
        governor.stop_reason = governor_state.get("stop_reason")
        governor.decisions = list(governor_state.get("decisions", []))
    best_params = restored_best_params if restored_best_params is not None else rng.uniform(-np.pi, np.pi, size=dim)
    current_params = restored_current_params if restored_current_params is not None else rng.uniform(-np.pi, np.pi, size=dim)
    objective_calls_used = int(extra_state.get("objective_calls_used", 0))
    objective_shots_used = int(extra_state.get("objective_shots_used", 0))

    def _evaluate_objective_accounted(params: np.ndarray, penalty_state: ConstraintPenaltyState, requested_shots: int) -> TailBatch:
        nonlocal objective_calls_used, objective_shots_used
        batch = runner.evaluate_objective(params, penalty_state, shots=requested_shots)
        objective_calls_used += 1
        objective_shots_used += int(batch.total_shots)
        return batch

    def _append_trace(evaluation: int, batch: TailBatch, penalty_state: ConstraintPenaltyState, params: np.ndarray, requested_shots: int) -> None:
        nonlocal best_energy, best_params
        if batch.feasible_best < best_energy:
            best_energy = float(batch.feasible_best)
            best_params = np.asarray(params, dtype=float).copy()
        trace.append(
            {
                "evaluation": float(evaluation),
                "objective": float(batch.cvar),
                "best_energy": float(best_energy),
                "approximation_gap": float(max(0.0, best_energy - problem.exact_feasible_energy)),
                "valid_ratio": float(batch.valid_ratio if math.isfinite(batch.valid_ratio) else float("nan")),
                "shots_used": float(batch.total_shots),
                "requested_shots": float(requested_shots),
                "penalty_linear": float(penalty_state.linear_strength),
                "penalty_quadratic": float(penalty_state.quadratic_strength),
                "penalty_epoch": float(penalty_state.epoch),
            }
        )
        penalty_controller.observe(batch, evaluation)
        governor.observe(evaluation, batch, best_energy)

    def _context(state: ConstraintPenaltyState) -> np.ndarray | None:
        if method not in {"bo_fourier", "bo_direct"} or not working_cfg.bo_contextual_penalty:
            return None
        return penalty_controller.penalty_context(state)

    def _governor_state() -> dict[str, Any]:
        return {
            "cumulative_shots": governor.cumulative_shots,
            "current_shots": governor.current_shots,
            "stagnant_steps": governor.stagnant_steps,
            "last_best_energy": governor.last_best_energy,
            "stop_reason": governor.stop_reason,
            "decisions": governor.decisions,
        }

    def _save_checkpoint(evaluation: int, params: np.ndarray | None, optimizer: GaussianProcessBayesOptimizer | None = None, extra: dict[str, Any] | None = None) -> None:
        if checkpoint_db_path is None or not working_cfg.runtime_checkpoint_enabled:
            return
        if evaluation % max(1, working_cfg.runtime_checkpoint_every) != 0:
            return
        extra_payload = dict(extra or {})
        extra_payload["shot_governor"] = _governor_state()
        extra_payload["objective_calls_used"] = int(objective_calls_used)
        extra_payload["objective_shots_used"] = int(objective_shots_used)
        payload = _checkpoint_payload(
            method=method,
            cfg=working_cfg,
            evaluation=evaluation,
            trace=trace,
            best_energy=best_energy,
            best_params=best_params,
            current_params=params,
            rng=rng,
            penalty_controller=penalty_controller,
            optimizer=optimizer,
            extra_state=extra_payload,
        )
        RunLedger.save_optimizer_checkpoint(checkpoint_db_path, run_key, method, payload)

    if method in {"bo_fourier", "bo_direct"}:
        optimizer = GaussianProcessBayesOptimizer(
            dim,
            working_cfg.sobol_init_iters,
            working_cfg.seed,
            context_dim=3 if working_cfg.bo_contextual_penalty else 0,
        )
        if optimizer_state is not None:
            optimizer = GaussianProcessBayesOptimizer.from_state_dict(optimizer_state)
        last_epoch = int(extra_state.get("last_epoch", -1))
        for evaluation in range(start_eval, total_steps + 1):
            if governor.should_stop():
                break
            requested_shots = governor.next_shots(evaluation)
            penalty_state = penalty_controller.state(evaluation)
            if penalty_state.epoch != last_epoch and evaluation > 1:
                optimizer.start_new_epoch(
                    strategy=working_cfg.bo_epoch_strategy if working_cfg.bo_reset_on_penalty_epoch or working_cfg.bo_epoch_strategy == "warm_start_reset" else "contextual",
                    incumbent=best_params,
                    warmstart_points=working_cfg.bo_epoch_warmstart_points,
                    penalty_context=_context(penalty_state),
                )
            last_epoch = penalty_state.epoch
            params = project_params(optimizer.suggest(context=_context(penalty_state)))
            batch = _evaluate_objective_accounted(params, penalty_state, requested_shots)
            optimizer.observe(params, batch.cvar, context=_context(penalty_state))
            _append_trace(evaluation, batch, penalty_state, params, requested_shots)
            _save_checkpoint(evaluation, params, optimizer, {"last_epoch": last_epoch})
        final_measurement = runner.sample_final_readout(best_params, penalty_controller.state(total_steps), shots=governor.final_readout_shots())
        metadata = runner.execution_metadata()
        metadata["shot_governor"] = governor.metadata()
        record = _record_from_trace(
            working_cfg,
            problem,
            method,
            trace,
            started_at,
            best_params,
            final_measurement.best_bitstring,
            metadata,
            objective_calls_used,
            objective_shots_used,
        )
        RunLedger.clear_optimizer_checkpoint(checkpoint_db_path, run_key) if checkpoint_db_path is not None else None
        return OptimizationOutcome(record=_finalize_qaoa_record(record, problem, working_cfg, final_measurement), best_params=np.asarray(best_params))

    if method == "random_fourier":
        for evaluation in range(start_eval, total_steps + 1):
            if governor.should_stop():
                break
            requested_shots = governor.next_shots(evaluation)
            params = rng.uniform(-np.pi, np.pi, size=dim)
            penalty_state = penalty_controller.state(evaluation)
            batch = _evaluate_objective_accounted(params, penalty_state, requested_shots)
            _append_trace(evaluation, batch, penalty_state, params, requested_shots)
            _save_checkpoint(evaluation, params)
        final_measurement = runner.sample_final_readout(best_params, penalty_controller.state(total_steps), shots=governor.final_readout_shots())
        metadata = runner.execution_metadata()
        metadata["shot_governor"] = governor.metadata()
        record = _record_from_trace(
            working_cfg,
            problem,
            method,
            trace,
            started_at,
            best_params,
            final_measurement.best_bitstring,
            metadata,
            objective_calls_used,
            objective_shots_used,
        )
        RunLedger.clear_optimizer_checkpoint(checkpoint_db_path, run_key) if checkpoint_db_path is not None else None
        return OptimizationOutcome(record=_finalize_qaoa_record(record, problem, working_cfg, final_measurement), best_params=np.asarray(best_params))

    def value_fn(vector: np.ndarray) -> float:
        state = penalty_controller.state(min(total_steps, len(trace) + 1))
        requested = governor.next_shots(min(total_steps, len(trace) + 1))
        return float(_evaluate_objective_accounted(vector, state, requested).cvar)

    last_epoch = int(extra_state.get("last_epoch", 0))
    epoch_local_step = int(extra_state.get("epoch_local_step", 0))
    params = np.asarray(current_params, dtype=float)
    for evaluation in range(start_eval, total_steps + 1):
        if governor.should_stop():
            break
        requested_shots = governor.next_shots(evaluation)
        penalty_state = penalty_controller.state(evaluation)
        if penalty_state.epoch != last_epoch:
            epoch_local_step = 0
            last_epoch = penalty_state.epoch
        epoch_local_step += 1
        decay_step = epoch_local_step if working_cfg.spsa_epoch_reset else evaluation
        step_size = working_cfg.spsa_epoch_step_boost * 0.18 / (decay_step ** 0.25)
        perturb = 0.12 / (decay_step ** 0.1)
        params, _ = spsa_step(params, value_fn, step_size, perturb, rng)
        batch = _evaluate_objective_accounted(params, penalty_state, requested_shots)
        _append_trace(evaluation, batch, penalty_state, params, requested_shots)
        _save_checkpoint(evaluation, params, None, {"last_epoch": last_epoch, "epoch_local_step": epoch_local_step})

    final_measurement = runner.sample_final_readout(best_params, penalty_controller.state(total_steps), shots=governor.final_readout_shots())
    metadata = runner.execution_metadata()
    metadata["shot_governor"] = governor.metadata()
    record = _record_from_trace(
        working_cfg,
        problem,
        method,
        trace,
        started_at,
        best_params,
        final_measurement.best_bitstring,
        metadata,
        objective_calls_used,
        objective_shots_used,
    )
    RunLedger.clear_optimizer_checkpoint(checkpoint_db_path, run_key) if checkpoint_db_path is not None else None
    return OptimizationOutcome(record=_finalize_qaoa_record(record, problem, working_cfg, final_measurement), best_params=np.asarray(best_params))


def _collect_single_problem_records(cfg: RunDeck, *, mitigation_sweep: bool = False) -> tuple[IsingSpinProblem, list[TrialResult]]:
    problem = IsingSpinProblem(cfg)
    records: list[TrialResult] = []
    records.extend(ClassicalBaselines(problem, cfg).run_all())
    if mitigation_sweep:
        qaoa_cfgs = [
            cfg.copy_with(parameterization="fourier", use_readout_mitigation=False, use_zne=False),
            cfg.copy_with(parameterization="fourier", use_readout_mitigation=True, use_zne=False),
            cfg.copy_with(parameterization="fourier", use_readout_mitigation=True, use_zne=True),
        ]
        for q_cfg in qaoa_cfgs:
            for method in QAOA_METHODS:
                eval_cfg = q_cfg.copy_with(parameterization="direct") if method == "bo_direct" else q_cfg.copy_with(parameterization="fourier")
                records.append(_evaluate_qaoa(eval_cfg, problem, method).record)
    else:
        records.append(_evaluate_qaoa(cfg.copy_with(parameterization="fourier"), problem, "bo_fourier").record)
        records.append(_evaluate_qaoa(cfg.copy_with(parameterization="fourier"), problem, "spsa_fourier").record)
        records.append(_evaluate_qaoa(cfg.copy_with(parameterization="fourier"), problem, "random_fourier").record)
        records.append(_evaluate_qaoa(cfg.copy_with(parameterization="direct"), problem, "bo_direct").record)
    return problem, records


def _persist_decision_outputs(cfg: RunDeck, records: list[TrialResult], summary_df: pd.DataFrame, decision_report: dict[str, Any], utility_frontier_df: pd.DataFrame) -> dict[str, Any]:
    ledger = RunLedger(cfg.tracker_experiment_name, tracker_backend=cfg.tracker_backend, tracker_uri=cfg.tracker_uri)
    ledger.log_config(cfg)
    summary = {
        "n_records": int(len(records)),
        "best_qaoa_record": _physics_rows(summary_df[summary_df["family"] == "qaoa"].sort_values("approximation_ratio")),
        "best_classical_record": _physics_rows(summary_df[summary_df["family"] == "classical_baseline"].sort_values("approximation_ratio")),
        "decision_report": decision_report,
        "mitigation_labels_evaluated": sorted(str(v) for v in summary_df[summary_df["family"] == "qaoa"]["mitigation_label"].dropna().unique().tolist()),
    }
    ledger.log_records(records)
    ledger.log_summary(summary)
    json_path = ledger.save_json(cfg.output_prefix)
    csv_path = ledger.save_csv(cfg.output_prefix)
    sqlite_path = ledger.save_sqlite(cfg.output_prefix)
    utility_frontier_path = Path(f"{cfg.output_prefix}_decision_utility_frontier.csv")
    utility_frontier_df.to_csv(utility_frontier_path, index=False)
    decision_json_path = Path(f"{cfg.output_prefix}_decision_report.json")
    decision_json_path.write_text(json_dumps_clean(decision_report, indent=2))

    recommendation = decision_report.get("recommendation", {})
    frontier_rows = decision_report.get("utility_frontier", [])[:3]
    rationale = recommendation.get("rationale", [])
    frontier_lines: list[str] = []
    for idx, row in enumerate(frontier_rows, start=1):
        frontier_lines.append(
            f"{idx}. `{row.get('method', 'unknown')}` ({row.get('family', 'unknown')}) — "
            f"utility={row.get('utility_score')}, approx_ratio={row.get('approximation_ratio')}, "
            f"runtime={row.get('runtime_seconds')}, shots={row.get('total_shots')}"
        )

    md_lines = [
        "# Decision Report",
        "",
        f"**Recommendation:** `{recommendation.get('recommendation', 'insufficient_data')}`",
        "",
        f"**Recommended method:** `{recommendation.get('recommended_method', 'unknown')}`",
        f"**Recommended family:** `{recommendation.get('recommended_family', 'unknown')}`",
        f"**Expected approximation ratio:** `{recommendation.get('expected_approximation_ratio')}`",
        f"**Expected valid ratio:** `{recommendation.get('expected_valid_ratio')}`",
        f"**Expected runtime (s):** `{recommendation.get('expected_runtime_seconds')}`",
        f"**Expected total shots:** `{recommendation.get('expected_total_shots')}`",
        f"**Utility score:** `{recommendation.get('utility_score')}`",
        "",
        "## Rationale",
        "",
        *[f"- {line}" for line in rationale],
        "",
        "## Top Utility Frontier Entries",
        "",
        *[f"- {line}" for line in frontier_lines],
        "",
        "## Warning",
        "",
        "This artifact captures a single-instance recommendation. Use the full study path for statistically stronger conclusions across lattice families, depths, noise levels, and shot budgets.",
    ]
    decision_md_path = Path(f"{cfg.output_prefix}_decision_report.md")
    decision_md_path.write_text("\n".join(md_lines).rstrip() + "\n")
    return {
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "sqlite_path": str(sqlite_path),
        "utility_frontier_path": str(utility_frontier_path),
        "decision_json_path": str(decision_json_path),
        "decision_md_path": str(decision_md_path),
    }


def run_smoke_test(cfg: RunDeck | None = None) -> dict[str, Any]:
    cfg = cfg or RunDeck(**DEFAULT_SMOKE_OVERRIDES)
    cfg.validate()
    set_reproducibility(cfg.seed)
    problem = IsingSpinProblem(cfg)
    outcome = _evaluate_qaoa(cfg.copy_with(use_zne=False, use_readout_mitigation=False), problem, "random_fourier")
    record = outcome.record
    return {
        "method": record.method,
        "seed": record.seed,
        "lattice_type": record.regime,
        "n_spins": record.n_assets,
        "magnetization_m": cfg.magnetization_m,
        "j2_ratio": record.j2_ratio,
        "disorder_strength": record.disorder_strength,
        "best_energy": record.best_energy,
        "exact_energy": record.exact_energy,
        "approximation_gap": record.approximation_gap,
        "approximation_ratio": record.approximation_ratio,
        "valid_ratio": record.valid_ratio,
        "valid_sector_ratio": record.valid_ratio,
        "success": record.success,
        "measurement_success_probability": record.measurement_success_probability,
        "final_bitstring": record.final_bitstring,
        "runtime_seconds": record.runtime_seconds,
        "total_shots": record.total_shots,
        "final_readout_shots": record.final_readout_shots,
        "objective_calls": record.objective_calls,
        "sampler_calls": record.sampler_calls,
        "transpilation_metadata": record.transpilation_metadata,
    }


def run_single_benchmark(cfg: RunDeck | None = None) -> dict[str, Any]:
    cfg = cfg or RunDeck()
    cfg.validate()
    set_reproducibility(cfg.seed)
    problem, records = _collect_single_problem_records(cfg, mitigation_sweep=False)
    summary_df = _summary_table(records)
    decision_report = build_decision_report(summary_df, cfg)
    return {
        "problem": {
            "lattice_type": problem.lattice_type,
            "j2_ratio": cfg.j2_ratio,
            "disorder_strength": cfg.disorder_strength,
            "J": problem.J.tolist(),
            "h": problem.h.tolist(),
            "exact_feasible_energy": problem.exact_feasible_energy,
            "frustration_index": problem.frustration_index,
            "energy_gap_to_second_lowest": problem.energy_gap_to_second_lowest,
            "lattice_metadata": problem.lattice_metadata,
        },
        "records": [physics_label_payload(record.as_dict()) for record in records],
        "decision_report": decision_report,
    }


def _budget_for_system_size(cfg: RunDeck, n_spins: int) -> int:
    if cfg.study_budget_ratio is not None:
        return max(1, min(n_spins, int(round(n_spins * cfg.study_budget_ratio))))
    if n_spins == cfg.n_assets:
        return cfg.budget
    scaled = cfg.budget / max(1, cfg.n_assets)
    return max(1, min(n_spins, int(round(n_spins * scaled))))


def _trial_grid(cfg: RunDeck) -> list[RunDeck]:
    grid: list[RunDeck] = []
    for j2_ratio in cfg.study_j2_ratios:
        for disorder_level in cfg.study_disorder_levels:
            for n_spins in cfg.study_n_assets:
                budget = _budget_for_system_size(cfg, n_spins)
                magnetization_m = 2 * budget - n_spins
                for seed in range(cfg.seed, cfg.seed + cfg.study_num_seeds):
                    for depth in cfg.study_depths:
                        for shot_budget in cfg.study_shot_budgets:
                            for noise_level in cfg.study_noise_levels:
                                grid.append(
                                    cfg.copy_with(
                                        lattice_type="j1j2_frustrated",
                                        j2_coupling=j2_ratio * cfg.j1_coupling,
                                        disorder_strength=disorder_level,
                                        n_spins=n_spins,
                                        magnetization_m=magnetization_m,
                                        seed=seed,
                                        depth=depth,
                                        base_shots=shot_budget,
                                        noise_level=noise_level,
                                    )
                                )
    return grid


def _build_trace_df(records: list[TrialResult]) -> pd.DataFrame:
    pd = load_pandas()
    rows: list[dict[str, Any]] = []
    for record in records:
        for step in record.trace:
            row = dict(step)
            row["method"] = record.method
            row["family"] = record.family
            row["seed"] = record.seed
            row["regime"] = record.regime
            row["lattice_type"] = record.regime
            row["n_assets"] = record.n_assets
            row["n_spins"] = record.n_assets
            row["budget"] = record.budget
            row["depth"] = record.depth
            row["noise_level"] = record.noise_level
            row["shot_budget"] = record.shot_budget
            row["j2_ratio"] = record.j2_ratio
            row["disorder_strength"] = record.disorder_strength
            row["frustration_index"] = record.frustration_index
            rows.append(row)
    return _with_physics_labels(pd.DataFrame(rows))


def _summary_table(records: list[TrialResult]) -> pd.DataFrame:
    pd = load_pandas()
    frame = pd.DataFrame([record.as_dict() for record in records])
    if "trace" in frame.columns:
        frame = frame.drop(columns=["trace"])
    if not frame.empty:
        call_denominator = frame.get("primitive_calls", frame["objective_calls"]).replace(0, np.nan)
        frame["runtime_per_call"] = frame["runtime_seconds"] / call_denominator
        frame["shots_per_call"] = frame["total_shots"] / call_denominator
        frame["run_cost"] = frame["runtime_seconds"].fillna(0.0) + 1e-6 * frame["total_shots"].fillna(0.0)
        frame["cost_normalized_gap"] = frame["approximation_gap"] * (1.0 + frame["run_cost"])
    return _with_physics_labels(frame)


def _bootstrap_ci(values: pd.Series, *, n_boot: int = 300, alpha: float = 0.05) -> tuple[float | None, float | None]:
    clean = values.dropna().to_numpy(dtype=float)
    if len(clean) < 2:
        return (None, None)
    rng = np.random.default_rng(DEFAULT_BOOTSTRAP['seed'])
    means = []
    for _ in range(n_boot):
        sample = rng.choice(clean, size=len(clean), replace=True)
        means.append(float(np.mean(sample)))
    return (float(np.quantile(means, alpha / 2.0)), float(np.quantile(means, 1.0 - alpha / 2.0)))


def _paired_delta_table(summary_df: pd.DataFrame, left_method: str, right_method: str, value_col: str) -> list[dict[str, Any]]:
    pd = load_pandas()
    mannwhitneyu = load_mannwhitneyu()
    frame = summary_df.copy()
    if frame.empty:
        return []
    frame["problem_id"] = frame.apply(_problem_label, axis=1)
    pair = frame[frame["method"].isin([left_method, right_method])][["problem_id", "method", value_col]].pivot_table(index="problem_id", columns="method", values=value_col)
    if left_method not in pair.columns or right_method not in pair.columns:
        return []
    delta = (pair[left_method] - pair[right_method]).dropna()
    if delta.empty:
        return []
    lo, hi = _bootstrap_ci(delta)
    return [{
        "left_method": left_method,
        "right_method": right_method,
        "metric": value_col,
        "mean_delta": float(delta.mean()),
        "median_delta": float(delta.median()),
        "ci_low": lo,
        "ci_high": hi,
        "win_rate_left": float((delta < 0).mean()),
    }]


def _sample_efficiency_auc(trace_df: pd.DataFrame, method: str) -> float | None:
    subset = trace_df[(trace_df["family"] == "qaoa") & (trace_df["method"] == method)].copy()
    if subset.empty:
        return None
    grouped = subset.groupby("evaluation")["best_energy"].mean().sort_index()
    if len(grouped) < 2:
        return float(grouped.iloc[0]) if len(grouped) == 1 else None
    x = grouped.index.to_numpy(dtype=float)
    y = grouped.to_numpy(dtype=float)
    return float(np.trapezoid(y, x) / max(x[-1] - x[0], 1.0))


def _mann_whitney(frame: pd.DataFrame, left_method: str, right_method: str, value_col: str) -> float | None:
    mannwhitneyu = load_mannwhitneyu()
    left = frame[frame["method"] == left_method][value_col].dropna().to_numpy(dtype=float)
    right = frame[frame["method"] == right_method][value_col].dropna().to_numpy(dtype=float)
    if len(left) < 2 or len(right) < 2:
        return None
    try:
        return float(mannwhitneyu(left, right, alternative="two-sided").pvalue)
    except Exception:
        return None


def _best_window(frame: pd.DataFrame, value_col: str, *, ascending: bool = False) -> dict[str, Any] | None:
    if frame.empty:
        return None
    row = frame.sort_values(value_col, ascending=ascending).iloc[0]
    payload = {
        "method": row.get("method"),
        "lattice_type": row.get("lattice_type", row.get("regime")),
        "n_spins": int(row.get("n_spins", row.get("n_assets"))) if row.get("n_spins", row.get("n_assets")) is not None else None,
        "budget": int(row.get("budget")) if row.get("budget") is not None else None,
        "depth": int(row.get("depth")) if row.get("depth") is not None else None,
        "noise_level": float(row.get("noise_level")) if row.get("noise_level") is not None else None,
        value_col: float(row.get(value_col)),
    }
    if row.get("j2_ratio") is not None:
        payload["j2_ratio"] = float(row.get("j2_ratio"))
    if row.get("disorder_strength") is not None:
        payload["disorder_strength"] = float(row.get("disorder_strength"))
    if row.get("frustration_index") is not None:
        payload["frustration_index"] = float(row.get("frustration_index"))
    if row.get("shot_budget") is not None:
        payload["shot_budget"] = int(row.get("shot_budget"))
    return payload


def _performance_profile(summary_df: pd.DataFrame) -> pd.DataFrame:
    pd = load_pandas()
    frame = summary_df[summary_df["method"] != "exact_feasible"].copy()
    if frame.empty:
        return pd.DataFrame(columns=["method", "tau", "rho"])
    frame["problem_id"] = frame.apply(_problem_label, axis=1)
    metric = frame[["problem_id", "method", "approximation_ratio"]].copy()
    best_by_problem = metric.groupby("problem_id")["approximation_ratio"].min().rename("best_ratio")
    metric = metric.merge(best_by_problem, on="problem_id", how="left")
    metric["perf_ratio"] = metric["approximation_ratio"] / metric["best_ratio"].clip(lower=1e-12)
    max_ratio = float(metric["perf_ratio"].replace([np.inf, -np.inf], np.nan).dropna().max()) if not metric.empty else 1.0
    max_ratio = max(1.1, min(max_ratio, 10.0))
    taus = np.linspace(1.0, max_ratio, num=80)
    rows: list[dict[str, float | str]] = []
    for method, chunk in metric.groupby("method"):
        values = chunk["perf_ratio"].to_numpy(dtype=float)
        for tau in taus:
            rows.append({"method": method, "tau": float(tau), "rho": float(np.mean(values <= tau))})
    return pd.DataFrame(rows)


def _build_findings_report(summary_df: pd.DataFrame, trace_df: pd.DataFrame, profile_df: pd.DataFrame) -> dict[str, Any]:
    pd = load_pandas()
    qaoa = summary_df[summary_df["family"] == "qaoa"].copy()
    question_1: dict[str, Any] = {
        "question": "Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency for frustrated ground-state search?",
        "bo_fourier_auc": _sample_efficiency_auc(trace_df, "bo_fourier"),
        "spsa_fourier_auc": _sample_efficiency_auc(trace_df, "spsa_fourier"),
        "p_value_gap": _mann_whitney(qaoa[qaoa["method"].isin(["bo_fourier", "spsa_fourier"])], "bo_fourier", "spsa_fourier", "approximation_gap"),
        "p_value_ratio": _mann_whitney(qaoa[qaoa["method"].isin(["bo_fourier", "spsa_fourier"])], "bo_fourier", "spsa_fourier", "approximation_ratio"),
    }
    bo_auc = question_1["bo_fourier_auc"]
    spsa_auc = question_1["spsa_fourier_auc"]
    if bo_auc is not None and spsa_auc is not None:
        question_1["winner"] = "bo_fourier" if bo_auc < spsa_auc else "spsa_fourier"
        question_1["delta_auc"] = float(spsa_auc - bo_auc)

    mitigation = (
        qaoa.groupby(
            ["method", "lattice_type", "n_spins", "budget", "depth", "noise_level", "shot_budget", "mitigation_label", "j2_ratio", "disorder_strength"],
            as_index=False,
        ).agg(mean_gap=("approximation_gap", "mean"), mean_psucc=("measurement_success_probability", "mean"), mean_valid_ratio=("valid_ratio", "mean"))
    )
    pivot_gap = mitigation.pivot_table(
        index=["method", "lattice_type", "n_spins", "budget", "depth", "noise_level", "shot_budget", "j2_ratio", "disorder_strength"],
        columns="mitigation_label",
        values="mean_gap",
    ).reset_index()
    pivot_psucc = mitigation.pivot_table(
        index=["method", "lattice_type", "n_spins", "budget", "depth", "noise_level", "shot_budget", "j2_ratio", "disorder_strength"],
        columns="mitigation_label",
        values="mean_psucc",
    ).reset_index()
    if "readout+zne" in pivot_gap.columns and "none" in pivot_gap.columns:
        pivot_gap["mitigation_gain"] = pivot_gap["none"] - pivot_gap["readout+zne"]
    else:
        pivot_gap["mitigation_gain"] = np.nan
    if "readout+zne" in pivot_psucc.columns and "none" in pivot_psucc.columns:
        pivot_psucc["psucc_gain"] = pivot_psucc["readout+zne"] - pivot_psucc["none"]
    else:
        pivot_psucc["psucc_gain"] = np.nan
    question_2 = {
        "question": "Does readout mitigation + ZNE materially improve ground-state quality at the frustrated point and nearby ratios?",
        "mean_gain": float(pivot_gap["mitigation_gain"].dropna().mean()) if pivot_gap["mitigation_gain"].notna().any() else None,
        "mean_psucc_gain": float(pivot_psucc["psucc_gain"].dropna().mean()) if pivot_psucc["psucc_gain"].notna().any() else None,
        "best_window": _best_window(pivot_gap.dropna(subset=["mitigation_gain"]), "mitigation_gain", ascending=False),
        "positive_gain_share": float((pivot_gap["mitigation_gain"] > 0).mean()) if pivot_gap["mitigation_gain"].notna().any() else None,
    }

    collapse = (
        qaoa.groupby(["method", "lattice_type", "n_spins", "budget", "depth", "noise_level", "j2_ratio", "disorder_strength"], as_index=False)
        .agg(
            mean_valid_ratio=("valid_ratio", "mean"),
            mean_gap=("approximation_gap", "mean"),
            mean_psucc=("measurement_success_probability", "mean"),
            mean_frustration_index=("frustration_index", "mean"),
        )
    )
    collapse["collapse_flag"] = collapse["mean_valid_ratio"] < 0.5
    question_3 = {
        "question": "How does valid-ratio collapse as system size, depth, and frustration ratio rise?",
        "collapse_share": float(collapse["collapse_flag"].mean()) if not collapse.empty else None,
        "first_collapse_window": _best_window(
            collapse[collapse["collapse_flag"]].sort_values(["n_spins", "j2_ratio", "depth", "noise_level"]).head(1),
            "mean_gap",
            ascending=False,
        ),
        "worst_valid_ratio_window": _best_window(collapse, "mean_valid_ratio", ascending=True),
    }

    fairness = (
        summary_df.groupby(["family", "method", "mitigation_label"], as_index=False)
        .agg(
            mean_gap=("approximation_gap", "mean"),
            mean_ratio=("approximation_ratio", "mean"),
            mean_psucc=("measurement_success_probability", "mean"),
            mean_runtime_seconds=("runtime_seconds", "mean"),
            mean_runtime_per_call=("runtime_per_call", "mean"),
            mean_total_shots=("total_shots", "mean"),
            mean_shots_per_call=("shots_per_call", "mean"),
            mean_objective_calls=("objective_calls", "mean"),
        )
        .sort_values(["mean_ratio", "mean_runtime_seconds", "mean_total_shots"])
    )
    profile_auc = (
        profile_df.groupby("method", as_index=False)["rho"].mean().rename(columns={"rho": "profile_area"}).sort_values("profile_area", ascending=False)
        if not profile_df.empty else pd.DataFrame(columns=["method", "profile_area"])
    )
    takeaway: list[str] = []
    if question_1.get("winner") is not None:
        takeaway.append(f"Matched-call sample efficiency favors {question_1['winner']}.")
    if question_2.get("best_window") is not None:
        best_window = question_2["best_window"]
        takeaway.append(
            "Mitigation helps most in a narrow window at "
            f"n={best_window['n_spins']}, J2/J1={best_window.get('j2_ratio')}, depth={best_window['depth']}, "
            f"noise={best_window['noise_level']:.3f}, shots={best_window.get('shot_budget', 0)}."
        )
    if question_3.get("collapse_share") is not None:
        takeaway.append(f"Valid-ratio collapse (<0.5) appears in {question_3['collapse_share']:.1%} of aggregated QAOA windows.")
    if not profile_auc.empty:
        takeaway.append(f"Best Dolan-Moré profile area: {profile_auc.iloc[0]['method']}.")

    ratio_ci = _bootstrap_ci(qaoa["approximation_ratio"]) if not qaoa.empty else (None, None)
    psucc_ci = _bootstrap_ci(qaoa["measurement_success_probability"]) if not qaoa.empty else (None, None)
    paired = []
    paired.extend(_paired_delta_table(summary_df, "bo_fourier", "spsa_fourier", "approximation_ratio"))
    paired.extend(_paired_delta_table(summary_df, "bo_fourier", "random_fourier", "approximation_ratio"))
    return {
        "question_1_sample_efficiency": question_1,
        "question_2_mitigation": question_2,
        "question_3_valid_ratio_collapse": question_3,
        "performance_profile_leaderboard": profile_auc.to_dict(orient="records"),
        "fairness_table": fairness.head(8).to_dict(orient="records"),
        "bootstrap_confidence_intervals": {
            "qaoa_approximation_ratio": {"low": ratio_ci[0], "high": ratio_ci[1]},
            "qaoa_p_succ": {"low": psucc_ci[0], "high": psucc_ci[1]},
        },
        "paired_method_deltas": paired,
        "takeaway": takeaway,
    }


def _render_markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Runtime-Aware J1-J2 Ising Findings Report", "", "## Explicit answers", ""]
    for key in ["question_1_sample_efficiency", "question_2_mitigation", "question_3_valid_ratio_collapse"]:
        block = report[key]
        lines.append(f"### {block['question']}")
        for metric, value in block.items():
            if metric == "question":
                continue
            lines.append(f"- **{metric}**: {value}")
        lines.append("")
    lines.append("## Performance profile")
    lines.append("")
    for row in report.get("performance_profile_leaderboard", [])[:5]:
        lines.append(f"- {row['method']}: profile_area={row['profile_area']:.4f}")
    lines.append("")
    lines.append("## Fairness snapshot")
    lines.append("")
    for row in report.get("fairness_table", []):
        lines.append(
            f"- {row['family']}::{row['method']} | mitigation={row['mitigation_label']} | mean_ratio={row['mean_ratio']:.6f} | "
            f"P_succ={row['mean_psucc']:.4f} | runtime={row['mean_runtime_seconds']:.4f}s | shots={row['mean_total_shots']:.1f}"
        )
    lines.append("")
    if report.get("paired_method_deltas"):
        lines.append("## Paired method deltas")
        lines.append("")
        for row in report["paired_method_deltas"]:
            lines.append(f"- {row['left_method']} vs {row['right_method']} | {row['metric']} mean_delta={row['mean_delta']:.6f} | win_rate_left={row['win_rate_left']:.3f}")
        lines.append("")
    lines.append("## Takeaway")
    lines.append("")
    for item in report.get("takeaway", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _render_latex_report(report: dict[str, Any]) -> str:
    sections = [r"\section*{Runtime-Aware J1--J2 Ising Findings Report}", r"\subsection*{Explicit answers}"]
    for key in ["question_1_sample_efficiency", "question_2_mitigation", "question_3_valid_ratio_collapse"]:
        block = report[key]
        sections.append(rf"\paragraph{{{block['question']}}}")
        sections.append(r"\begin{itemize}")
        for metric, value in block.items():
            if metric == "question":
                continue
            sections.append(rf"\item \textbf{{{metric}}}: {value}")
        sections.append(r"\end{itemize}")
    sections.append(r"\subsection*{Performance profile leaderboard}")
    sections.append(r"\begin{itemize}")
    for row in report.get("performance_profile_leaderboard", [])[:5]:
        sections.append(rf"\item {row['method']}: profile\_area={row['profile_area']:.4f}")
    sections.append(r"\end{itemize}")
    if report.get("paired_method_deltas"):
        sections.append(r"\subsection*{Paired method deltas}")
        sections.append(r"\begin{itemize}")
        for row in report["paired_method_deltas"]:
            sections.append(rf"\item {row['left_method']} vs {row['right_method']}: mean\_delta={row['mean_delta']:.6f}, win\_rate\_left={row['win_rate_left']:.3f}")
        sections.append(r"\end{itemize}")
    sections.append(r"\subsection*{Takeaway}")
    sections.append(r"\begin{itemize}")
    for item in report.get("takeaway", []):
        sections.append(rf"\item {item}")
    sections.append(r"\end{itemize}")
    return "\n".join(sections) + "\n"


def _render_executive_summary(findings_report: dict[str, Any], decision_report: dict[str, Any]) -> str:
    recommendation = decision_report.get("recommendation", {})
    lines = [
        "# Runtime-Aware J1-J2 Ising Executive Summary",
        "",
        "## Core questions",
        "- Does BO-tuned Fourier QAOA outperform SPSA-tuned QAOA in sample efficiency for frustrated ground-state search?",
        "- When does mitigation materially improve ground-state quality near the maximally frustrated ratio?",
        "- How does valid-ratio collapse as system size, depth, and frustration increase?",
        "",
        "## Recommended execution stance",
        f"- recommendation: **{recommendation.get('recommendation', 'unknown')}**",
        f"- recommended method: **{recommendation.get('recommended_method', 'unknown')}**",
        f"- expected approximation ratio: **{recommendation.get('expected_approximation_ratio', 'n/a')}**",
        f"- expected valid ratio: **{recommendation.get('expected_valid_ratio', 'n/a')}**",
        "",
        "## Key takeaways",
    ]
    for item in findings_report.get("takeaway", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## Honest limitation",
        "- This package is runtime-aware and recovery-aware, but should not be labeled live IBM hardware certified until the session-recovery harness is exercised on a real backend.",
        "",
    ])
    return "\n".join(lines)


def _write_study_progress(output_prefix: str, payload: dict[str, Any]) -> Path:
    progress_path = Path(f"{output_prefix}_progress.json")
    progress_path.write_text(json_dumps_clean(payload, indent=2))
    return progress_path


def run_advisor(cfg: RunDeck | None = None) -> dict[str, Any]:
    pd = load_pandas()
    cfg = cfg or RunDeck()
    cfg.validate()
    set_reproducibility(cfg.seed)
    problem, records = _collect_single_problem_records(cfg, mitigation_sweep=True)
    summary_df = _summary_table(records)
    utility_frontier_df = compute_utility_frontier(summary_df, cfg)
    decision_report = build_decision_report(summary_df, cfg)
    recommendation = decision_report.get("recommendation", {})
    artifact_paths = _persist_decision_outputs(cfg, records, summary_df, decision_report, utility_frontier_df)
    mitigation_labels = sorted(str(v) for v in summary_df[summary_df["family"] == "qaoa"]["mitigation_label"].dropna().unique().tolist())
    return {
        "mode": "decision",
        "problem": {
            "lattice_type": problem.lattice_type,
            "j2_ratio": cfg.j2_ratio,
            "disorder_strength": cfg.disorder_strength,
            "J": problem.J.tolist(),
            "h": problem.h.tolist(),
            "exact_feasible_energy": problem.exact_feasible_energy,
            "frustration_index": problem.frustration_index,
            "energy_gap_to_second_lowest": problem.energy_gap_to_second_lowest,
            "lattice_metadata": problem.lattice_metadata,
        },
        "decision_report": decision_report,
        "utility_frontier": utility_frontier_df.to_dict(orient="records"),
        "recommended_method": recommendation.get("recommended_method"),
        "recommended_family": recommendation.get("recommended_family"),
        "recommendation": recommendation.get("recommendation"),
        "rationale": recommendation.get("rationale", []),
        "mitigation_labels_evaluated": mitigation_labels,
        "mitigation_sweep_complete": set(mitigation_labels) >= {"none", "readout", "readout+zne"},
        "artifacts": artifact_paths,
    }


def run_benchmark_study(cfg: RunDeck | None = None, *, progress_callback: Any | None = None) -> dict[str, Any]:
    pd = load_pandas()
    cfg = cfg or RunDeck()
    cfg.validate()
    logger = setup_logging("runtime_aware_qaoa")
    ledger = RunLedger(cfg.tracker_experiment_name, tracker_backend=cfg.tracker_backend, tracker_uri=cfg.tracker_uri)
    ledger.log_config(cfg)
    sqlite_path = Path(f"{cfg.output_prefix}_{ledger.timestamp}.sqlite")
    RunLedger.initialize_sqlite(sqlite_path)

    records: list[TrialResult] = []
    grid = _trial_grid(cfg)
    total_trials = len(grid)
    progress_path = _write_study_progress(cfg.output_prefix, {"event": "study_started", "total_trials": total_trials, "completed_trials": 0, "output_prefix": cfg.output_prefix})
    if progress_callback is not None:
        progress_callback({"event": "study_started", "total_trials": total_trials, "completed_trials": 0, "progress_path": str(progress_path)})
    for index, trial_cfg in enumerate(grid, start=1):
        set_reproducibility(trial_cfg.seed)
        problem = IsingSpinProblem(trial_cfg)
        records.extend(ClassicalBaselines(problem, trial_cfg).run_all())

        qaoa_cfgs = [
            trial_cfg.copy_with(parameterization="fourier", use_readout_mitigation=False, use_zne=False),
            trial_cfg.copy_with(parameterization="fourier", use_readout_mitigation=True, use_zne=False),
            trial_cfg.copy_with(parameterization="fourier", use_readout_mitigation=True, use_zne=True),
        ]
        method_sequence = ["bo_fourier", "spsa_fourier", "random_fourier", "bo_direct"]
        for q_cfg in qaoa_cfgs:
            for method in method_sequence:
                records.append(_evaluate_qaoa(q_cfg, problem, method, checkpoint_db_path=sqlite_path).record)

        logger.info(
            "trial %d/%d complete",
            index,
            total_trials,
        )

        partial_summary_df = _summary_table(records)
        progress_payload = {
            "event": "trial_complete",
            "completed_trials": index,
            "total_trials": total_trials,
            "latest_trial": {
                "lattice_type": trial_cfg.lattice_type,
                "n_spins": trial_cfg.n_spins,
                "budget": trial_cfg.budget,
                "magnetization_m": trial_cfg.magnetization_m,
                "j2_ratio": trial_cfg.j2_ratio,
                "disorder_strength": trial_cfg.disorder_strength,
                "seed": trial_cfg.seed,
                "depth": trial_cfg.depth,
                "shot_budget": trial_cfg.base_shots,
                "noise_level": trial_cfg.noise_level,
            },
            "partial_record_count": len(records),
            "partial_best_qaoa": _physics_rows(partial_summary_df[partial_summary_df["family"] == "qaoa"].sort_values("approximation_ratio")),
            "partial_best_classical": _physics_rows(partial_summary_df[partial_summary_df["family"] == "classical_baseline"].sort_values("approximation_ratio")),
        }
        progress_path = _write_study_progress(cfg.output_prefix, progress_payload)
        if progress_callback is not None:
            callback_payload = dict(progress_payload)
            callback_payload["progress_path"] = str(progress_path)
            progress_callback(callback_payload)

    summary_df = _summary_table(records)
    trace_df = _build_trace_df(records)
    profile_df = _performance_profile(summary_df)
    output_root = Path(cfg.output_prefix)
    output_root.parent.mkdir(parents=True, exist_ok=True)

    if not trace_df.empty:
        plot_approximation_gap_vs_evaluations(trace_df, output_root.with_name(output_root.name + "_approx_gap.png"))
        plot_qaoa_optimizer_sample_efficiency(trace_df, output_root.with_name(output_root.name + "_sample_efficiency.png"))
    plot_success_probability_vs_noise(summary_df, output_root.with_name(output_root.name + "_success_vs_noise.png"))
    plot_valid_ratio_vs_depth(summary_df, output_root.with_name(output_root.name + "_valid_ratio_vs_depth.png"))
    plot_valid_sector_ratio_vs_spins(summary_df, output_root.with_name(output_root.name + "_valid_sector_ratio_vs_spins.png"))
    plot_energy_gap_vs_j2_ratio(summary_df, output_root.with_name(output_root.name + "_energy_gap_vs_j2_ratio.png"))
    plot_mitigation_gain_vs_shot_budget(summary_df, output_root.with_name(output_root.name + "_mitigation_vs_shots.png"))
    plot_performance_profile(profile_df, output_root.with_name(output_root.name + "_performance_profile.png"))

    grouped = (
        summary_df.groupby(
            ["family", "method", "lattice_type", "n_spins", "budget", "noise_level", "depth", "shot_budget", "mitigation_label", "j2_ratio", "disorder_strength"],
            dropna=False,
        )
        .agg(
            mean_best_energy=("best_energy", "mean"),
            std_best_energy=("best_energy", "std"),
            mean_gap=("approximation_gap", "mean"),
            mean_ratio=("approximation_ratio", "mean"),
            median_best_energy=("best_energy", "median"),
            success_probability=("success", "mean"),
            p_succ=("measurement_success_probability", "mean"),
            mean_valid_ratio=("valid_ratio", "mean"),
            mean_frustration_index=("frustration_index", "mean"),
            mean_runtime_seconds=("runtime_seconds", "mean"),
            mean_runtime_per_call=("runtime_per_call", "mean"),
            mean_total_shots=("total_shots", "mean"),
            mean_shots_per_call=("shots_per_call", "mean"),
            mean_objective_calls=("objective_calls", "mean"),
        )
        .reset_index()
    )

    findings_report = _build_findings_report(summary_df, trace_df, profile_df)
    utility_frontier_df = compute_utility_frontier(summary_df, cfg)
    decision_report = build_decision_report(summary_df, cfg)
    executive_summary = _render_executive_summary(findings_report, decision_report)
    summary = {
        "n_records": int(len(records)),
        "n_trials": total_trials,
        "best_qaoa_record": _physics_rows(summary_df[summary_df["family"] == "qaoa"].sort_values("approximation_ratio")),
        "best_classical_record": _physics_rows(summary_df[summary_df["family"] == "classical_baseline"].sort_values("approximation_ratio")),
        "aggregates": grouped.to_dict(orient="records"),
        "findings_report": findings_report,
        "decision_report": decision_report,
    }

    ledger.log_records(records)
    ledger.log_summary(summary)
    json_path = ledger.save_json(cfg.output_prefix)
    csv_path = ledger.save_csv(cfg.output_prefix)
    sqlite_path = ledger.save_sqlite(cfg.output_prefix, existing_path=sqlite_path)
    grouped_path = Path(f"{cfg.output_prefix}_aggregates.csv")
    grouped.to_csv(grouped_path, index=False)
    perf_profile_path = Path(f"{cfg.output_prefix}_performance_profile.csv")
    profile_df.to_csv(perf_profile_path, index=False)
    findings_json_path = Path(f"{cfg.output_prefix}_findings.json")
    findings_json_path.write_text(json_dumps_clean(findings_report, indent=2))
    findings_md_path = Path(f"{cfg.output_prefix}_findings.md")
    findings_md_path.write_text(_render_markdown_report(findings_report))
    findings_tex_path = Path(f"{cfg.output_prefix}_findings.tex")
    findings_tex_path.write_text(_render_latex_report(findings_report))
    utility_frontier_path = Path(f"{cfg.output_prefix}_utility_frontier.csv")
    utility_frontier_df.to_csv(utility_frontier_path, index=False)
    decision_json_path = Path(f"{cfg.output_prefix}_decision_report.json")
    decision_json_path.write_text(json_dumps_clean(decision_report, indent=2))
    decision_md_path = Path(f"{cfg.output_prefix}_decision_report.md")
    decision_md_path.write_text(_render_executive_summary(findings_report, decision_report))
    executive_summary_path = Path(f"{cfg.output_prefix}_executive_summary.md")
    executive_summary_path.write_text(executive_summary)

    result = {
        "summary": summary,
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "sqlite_path": str(sqlite_path),
        "aggregates_path": str(grouped_path),
        "performance_profile_path": str(perf_profile_path),
        "findings_json_path": str(findings_json_path),
        "findings_md_path": str(findings_md_path),
        "findings_tex_path": str(findings_tex_path),
        "utility_frontier_path": str(utility_frontier_path),
        "decision_json_path": str(decision_json_path),
        "decision_md_path": str(decision_md_path),
        "executive_summary_path": str(executive_summary_path),
    }
    progress_path = _write_study_progress(cfg.output_prefix, {"event": "study_complete", "completed_trials": total_trials, "total_trials": total_trials, "result": sanitize_json_payload(result)})
    if progress_callback is not None:
        progress_callback({
            "event": "study_complete",
            "completed_trials": total_trials,
            "total_trials": total_trials,
            "progress_path": str(progress_path),
            "artifacts": sanitize_json_payload({
                "json_path": str(json_path),
                "csv_path": str(csv_path),
                "sqlite_path": str(sqlite_path),
                "aggregates_path": str(grouped_path),
                "performance_profile_path": str(perf_profile_path),
                "findings_json_path": str(findings_json_path),
                "findings_md_path": str(findings_md_path),
                "findings_tex_path": str(findings_tex_path),
                "utility_frontier_path": str(utility_frontier_path),
                "decision_json_path": str(decision_json_path),
                "decision_md_path": str(decision_md_path),
                "executive_summary_path": str(executive_summary_path),
            }),
            "best_qaoa_record": summary.get("best_qaoa_record", []),
            "best_classical_record": summary.get("best_classical_record", []),
        })
    return result


def run_experiment(cfg: RunDeck | None = None) -> dict[str, Any]:
    return run_benchmark_study(cfg)


run_decision = run_advisor

__all__ = [
    'QAOA_METHODS',
    'PenaltyController',
    'OptimizationOutcome',
    'run_smoke_test',
    'run_single_benchmark',
    'run_decision',
    'run_advisor',
    'run_benchmark_study',
    'run_experiment',
]
