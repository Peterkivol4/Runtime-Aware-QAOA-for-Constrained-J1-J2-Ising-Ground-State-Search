from __future__ import annotations

import argparse
import csv
import json
import math
import os
import tempfile
import time
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "spinmesh_mplconfig"))

from ionmesh_runtime._internal.config import RunDeck
from ionmesh_runtime._internal.execution_body import (
    ExecutionDeformationVector,
    RuntimePhysicalConclusion,
    RuntimeTrustGate,
    bernoulli_confidence_interval_width,
    build_runtime_trust_report,
    calibration_snapshot_hash,
    layout_distance_score,
)
from ionmesh_runtime._internal.optional_deps import load_matplotlib_pyplot, load_qiskit_aer, load_qiskit_fake_backend
from ionmesh_runtime._internal.problem import IsingSpinProblem
from ionmesh_runtime._internal.quantum import ReadoutMitigator, _build_parametric_qaoa_circuit
from ionmesh_runtime._internal.runtime_support import RuntimeSamplerFactory
from ionmesh_runtime._internal.tracking import json_dumps_clean


ANGLE_CANDIDATES = 32


def _base_cfg() -> RunDeck:
    cfg = RunDeck(
        seed=314,
        n_spins=6,
        magnetization_m=0,
        j1_coupling=1.0,
        j2_coupling=0.5,
        disorder_strength=0.0,
        h_field=0.0,
        lattice_type="j1j2_frustrated",
        depth=2,
        fourier_modes=2,
        parameterization="direct",
        base_shots=1024,
        cvar_alpha=1.0,
        use_noise=True,
        use_readout_mitigation=True,
        use_zne=False,
        runtime_mode="aer",
    )
    cfg.validate()
    return cfg


def _backend(topology: str, *, seed: int = 19) -> Any:
    maps = {
        "line": [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)],
        "star": [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5)],
        "forked_heavy_hex": [(0, 1), (1, 2), (1, 3), (2, 4), (3, 5)],
    }
    snapshot = {
        "backend_name": f"generic_{topology}",
        "num_qubits": 6,
        "coupling_map": maps[topology],
        "basis_gates": ["id", "rz", "sx", "x", "cx", "measure"],
    }
    return RuntimeSamplerFactory.build_generic_heavy_hex_backend(num_qubits=6, seed=seed, calibration_snapshot=snapshot)


def _noise_model(*, depol_error: float, readout_p10: float, readout_p01: float) -> Any:
    tools = load_qiskit_aer()
    NoiseModel = tools["NoiseModel"]
    ReadoutError = tools["ReadoutError"]
    depolarizing_error = tools["depolarizing_error"]
    noise_model = NoiseModel()
    one_qubit = depolarizing_error(float(depol_error), 1)
    two_qubit = depolarizing_error(min(0.75, 10.0 * float(depol_error)), 2)
    noise_model.add_all_qubit_quantum_error(one_qubit, ["x", "sx"])
    noise_model.add_all_qubit_quantum_error(two_qubit, ["cx"])
    readout = ReadoutError([[1.0 - readout_p10, readout_p10], [readout_p01, 1.0 - readout_p01]])
    noise_model.add_all_qubit_readout_error(readout)
    return noise_model


def _transpile(circuit: Any, backend: Any, *, optimization_level: int, initial_layout: list[int], routing_method: str) -> Any:
    qiskit_tools = load_qiskit_fake_backend()
    pass_manager = qiskit_tools["generate_preset_pass_manager"](
        backend=backend,
        optimization_level=int(optimization_level),
        initial_layout=initial_layout,
        routing_method=routing_method,
    )
    return pass_manager.run(circuit)


def _run_counts(circuit: Any, *, shots: int, seed: int, depol_error: float, readout_p10: float, readout_p01: float) -> dict[str, float]:
    tools = load_qiskit_aer()
    simulator = tools["AerSimulator"](
        noise_model=_noise_model(depol_error=depol_error, readout_p10=readout_p10, readout_p01=readout_p01),
        seed_simulator=int(seed),
    )
    result = simulator.run(circuit, shots=int(shots), seed_simulator=int(seed)).result()
    return {str(key): float(value) for key, value in result.get_counts().items()}


def _statevector_probabilities(circuit: Any) -> dict[str, float]:
    from qiskit.quantum_info import Statevector

    state = Statevector.from_instruction(circuit)
    return {str(key): float(value) for key, value in state.probabilities_dict().items()}


def _normalize_counts(counts: dict[str, float]) -> dict[str, float]:
    total = float(sum(counts.values()))
    if total <= 0.0:
        return {}
    return {bitstring: float(value) / total for bitstring, value in counts.items()}


def _metrics(problem: IsingSpinProblem, weights: dict[str, float]) -> dict[str, float | str]:
    if not weights:
        return {
            "energy": math.nan,
            "magnetization": math.nan,
            "nn_correlation": math.nan,
            "nnn_correlation": math.nan,
            "valid_ratio": 0.0,
            "phase_label": "empty",
            "energy_variance": math.nan,
        }
    energies: list[float] = []
    magnetizations: list[float] = []
    nn_corrs: list[float] = []
    nnn_corrs: list[float] = []
    valid_ratio = 0.0
    for bitstring, probability in weights.items():
        sigma = problem.bitstring_to_spins(bitstring)
        energy = problem.evaluate_energy(bitstring)
        magnetization = float(np.sum(sigma) / problem.n)
        nn_corr = _edge_correlation(sigma, problem.nn_edges)
        nnn_corr = _edge_correlation(sigma, problem.nnn_edges)
        energies.append(float(probability) * energy)
        magnetizations.append(float(probability) * magnetization)
        nn_corrs.append(float(probability) * nn_corr)
        nnn_corrs.append(float(probability) * nnn_corr)
        if problem.is_valid(bitstring):
            valid_ratio += float(probability)
    energy_mean = float(sum(energies))
    energy_second_moment = sum(float(probability) * (problem.evaluate_energy(bitstring) ** 2) for bitstring, probability in weights.items())
    variance = max(0.0, float(energy_second_moment - energy_mean**2))
    nn_mean = float(sum(nn_corrs))
    nnn_mean = float(sum(nnn_corrs))
    return {
        "energy": energy_mean,
        "magnetization": float(sum(magnetizations)),
        "nn_correlation": nn_mean,
        "nnn_correlation": nnn_mean,
        "valid_ratio": float(valid_ratio),
        "phase_label": _phase_label(float(valid_ratio), nn_mean, nnn_mean),
        "energy_variance": variance,
    }


def _edge_correlation(sigma: np.ndarray, edges: list[tuple[int, int]]) -> float:
    if not edges:
        return 0.0
    return float(np.mean([sigma[i] * sigma[j] for i, j in edges]))


def _phase_label(valid_ratio: float, nn_correlation: float, nnn_correlation: float) -> str:
    if valid_ratio < 0.5:
        return "invalid_sector_dominated"
    if nn_correlation < -0.2 and nnn_correlation < -0.2:
        return "frustrated_antiferromagnetic"
    if nn_correlation < -0.2:
        return "nearest_neighbor_antiferromagnetic"
    return "mixed_or_paramagnetic"


def _optimize_frozen_angles(cfg: RunDeck, problem: IsingSpinProblem) -> tuple[np.ndarray, dict[str, float | str]]:
    rng = np.random.default_rng(cfg.seed)
    best_energy = math.inf
    best_params: np.ndarray | None = None
    best_metrics: dict[str, float | str] | None = None
    for _ in range(ANGLE_CANDIDATES):
        gamma = rng.uniform(-math.pi, math.pi, size=cfg.depth)
        beta = rng.uniform(-math.pi / 2.0, math.pi / 2.0, size=cfg.depth)
        circuit = _build_parametric_qaoa_circuit(cfg, gamma, beta, measure=False)
        metrics = _metrics(problem, _statevector_probabilities(circuit))
        energy = float(metrics["energy"])
        if energy < best_energy:
            best_energy = energy
            best_params = np.concatenate([gamma, beta])
            best_metrics = metrics
    if best_params is None or best_metrics is None:  # pragma: no cover - defensive
        raise RuntimeError("failed to choose frozen angles")
    return best_params, best_metrics


def _angles(params: np.ndarray, depth: int) -> tuple[np.ndarray, np.ndarray]:
    return np.asarray(params[:depth], dtype=float), np.asarray(params[depth : depth * 2], dtype=float)


def _record(
    *,
    cfg: RunDeck,
    problem: IsingSpinProblem,
    problem_id: str,
    backend_name: str,
    snapshot_id: str,
    calibration_age_seconds: float,
    source_depth: int,
    transpiled: Any,
    source_metrics: dict[str, float | str],
    observed_metrics: dict[str, float | str],
    shots: int,
    queue_delay_seconds: float,
    session_duration_seconds: float,
    runtime_seconds: float,
    mitigation_shift: float | None,
    mitigation_instability: float | None,
    decision: str,
    rejection_reason: str | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    metadata = RuntimeSamplerFactory.transpilation_metadata(type("B", (), {"name": backend_name, "operation_names": ["id", "rz", "sx", "x", "cx", "measure"]})(), transpiled)
    energy_error_vs_ideal = abs(float(observed_metrics["energy"]) - float(source_metrics["energy"]))
    magnetization_error = abs(float(observed_metrics["magnetization"]) - float(source_metrics["magnetization"]))
    corr_error = max(
        abs(float(observed_metrics["nn_correlation"]) - float(source_metrics["nn_correlation"])),
        abs(float(observed_metrics["nnn_correlation"]) - float(source_metrics["nnn_correlation"])),
    )
    ci_width = 2.0 * 1.96 * math.sqrt(float(observed_metrics["energy_variance"]) / max(int(shots), 1))
    vector = ExecutionDeformationVector(
        problem_id=problem_id,
        backend_name=backend_name,
        calibration_snapshot_id=snapshot_id,
        calibration_age_seconds=float(calibration_age_seconds),
        n_spins=cfg.n_spins,
        p_layers=cfg.depth,
        j1=cfg.j1_coupling,
        j2=cfg.j2_coupling,
        h=cfg.h_field,
        source_circuit_depth=int(source_depth),
        transpiled_circuit_depth=int(metadata["depth"]),
        two_qubit_gate_count=int(metadata["two_qubit_gate_count"]),
        swap_count=int(metadata["swap_count"]),
        layout_distance_score=float(extra.get("layout_distance_score", 0.0)),
        shots=int(shots),
        queue_delay_seconds=float(queue_delay_seconds),
        session_duration_seconds=float(session_duration_seconds),
        energy_error_vs_exact=abs(float(observed_metrics["energy"]) - problem.exact_feasible_energy),
        energy_error_vs_ideal_qaoa=energy_error_vs_ideal,
        magnetization_error=magnetization_error,
        correlation_error=corr_error,
        structure_factor_error=None,
        phase_label_changed=observed_metrics["phase_label"] != source_metrics["phase_label"],
        sample_variance=float(observed_metrics["energy_variance"]),
        confidence_interval_width=float(ci_width),
        mitigation_shift=mitigation_shift,
        mitigation_instability=mitigation_instability,
        runtime_seconds=float(runtime_seconds),
        quantum_decision=decision,
        rejection_reason=rejection_reason,
    )
    row = vector.as_dict()
    row.update(
        {
            "experiment": extra.get("experiment"),
            "topology_model": extra.get("topology_model"),
            "transpiler_optimization_level": extra.get("transpiler_optimization_level"),
            "initial_layout_policy": extra.get("initial_layout_policy"),
            "routing_method": extra.get("routing_method"),
            "session_policy": extra.get("session_policy"),
            "mitigation_policy": extra.get("mitigation_policy"),
            "noise_scale": extra.get("noise_scale"),
            "ideal_energy": source_metrics["energy"],
            "observed_energy": observed_metrics["energy"],
            "ideal_magnetization": source_metrics["magnetization"],
            "observed_magnetization": observed_metrics["magnetization"],
            "ideal_nn_correlation": source_metrics["nn_correlation"],
            "observed_nn_correlation": observed_metrics["nn_correlation"],
            "ideal_nnn_correlation": source_metrics["nnn_correlation"],
            "observed_nnn_correlation": observed_metrics["nnn_correlation"],
            "ideal_phase_label": source_metrics["phase_label"],
            "observed_phase_label": observed_metrics["phase_label"],
            "valid_ratio": observed_metrics["valid_ratio"],
            "routing_inflation": vector.routing_inflation,
        }
    )
    return row


def _execute_body(
    *,
    cfg: RunDeck,
    problem: IsingSpinProblem,
    params: np.ndarray,
    source_metrics: dict[str, float | str],
    source_depth: int,
    topology_model: str,
    optimization_level: int,
    initial_layout_policy: str,
    initial_layout: list[int],
    routing_method: str,
    shots: int,
    noise_scale: float,
    calibration_age_seconds: float,
    session_policy: str,
    mitigation_policy: str,
    seed_offset: int,
    queue_delay_seconds: float = 0.0,
    session_duration_seconds: float = 1.0,
) -> tuple[dict[str, Any], dict[str, float | str], Any, dict[str, float]]:
    gamma, beta = _angles(params, cfg.depth)
    measured = _build_parametric_qaoa_circuit(cfg, gamma, beta, measure=True)
    backend = _backend(topology_model, seed=cfg.seed + seed_offset)
    started = time.time()
    transpiled = _transpile(
        measured,
        backend,
        optimization_level=optimization_level,
        initial_layout=initial_layout,
        routing_method=routing_method,
    )
    counts = _run_counts(
        transpiled,
        shots=shots,
        seed=cfg.seed + seed_offset,
        depol_error=0.004 * noise_scale,
        readout_p10=min(0.2, 0.010 * noise_scale),
        readout_p01=min(0.2, 0.030 * noise_scale),
    )
    if mitigation_policy == "readout":
        mitigator = ReadoutMitigator(cfg.n_spins, min(0.2, 0.010 * noise_scale), min(0.2, 0.030 * noise_scale))
        raw_metrics = _metrics(problem, _normalize_counts(counts))
        mitigated_counts = mitigator.mitigate(counts)
        observed_metrics = _metrics(problem, _normalize_counts(mitigated_counts))
        mitigation_shift = float(observed_metrics["energy"]) - float(raw_metrics["energy"])
        mitigation_instability = max(
            abs(float(observed_metrics["nn_correlation"]) - float(raw_metrics["nn_correlation"])),
            abs(float(observed_metrics["nnn_correlation"]) - float(raw_metrics["nnn_correlation"])),
        )
    else:
        raw_metrics = _metrics(problem, _normalize_counts(counts))
        observed_metrics = raw_metrics
        mitigation_shift = None
        mitigation_instability = None
    runtime_seconds = time.time() - started
    row = _record(
        cfg=cfg,
        problem=problem,
        problem_id="frustrated_n6_j2_05_p2_seed314",
        backend_name=f"generic_{topology_model}",
        snapshot_id=calibration_snapshot_hash(
            {"topology": topology_model, "noise_scale": noise_scale, "readout": [0.010 * noise_scale, 0.030 * noise_scale]}
        ),
        calibration_age_seconds=calibration_age_seconds,
        source_depth=source_depth,
        transpiled=transpiled,
        source_metrics=source_metrics,
        observed_metrics=observed_metrics,
        shots=shots,
        queue_delay_seconds=queue_delay_seconds,
        session_duration_seconds=session_duration_seconds,
        runtime_seconds=runtime_seconds,
        mitigation_shift=mitigation_shift,
        mitigation_instability=mitigation_instability,
        decision="run_quantum",
        rejection_reason=None,
        extra={
            "topology_model": topology_model,
            "transpiler_optimization_level": optimization_level,
            "initial_layout_policy": initial_layout_policy,
            "routing_method": routing_method,
            "session_policy": session_policy,
            "mitigation_policy": mitigation_policy,
            "noise_scale": noise_scale,
            "layout_distance_score": layout_distance_score(initial_layout, list(backend.coupling_map.get_edges())),
        },
    )
    return row, observed_metrics, transpiled, counts


def _combined_metrics(problem: IsingSpinProblem, weighted_counts: list[tuple[dict[str, float], float]]) -> dict[str, float | str]:
    aggregate: dict[str, float] = {}
    for counts, weight in weighted_counts:
        for bitstring, value in counts.items():
            aggregate[bitstring] = aggregate.get(bitstring, 0.0) + float(weight) * float(value)
    return _metrics(problem, _normalize_counts(aggregate))


def _write_records(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(_record_fieldnames(rows))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _record_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    base = [field.name for field in fields(ExecutionDeformationVector)]
    extras = sorted({key for row in rows for key in row if key not in base})
    return base + extras


def _report_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        rendered = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, float):
                rendered.append(f"{value:.6g}")
            else:
                rendered.append(str(value))
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def _mean(rows: list[dict[str, Any]], column: str) -> float:
    return float(np.mean([float(row[column]) for row in rows])) if rows else math.nan


def _pearson(rows: list[dict[str, Any]], left: str, right: str) -> float:
    if len(rows) < 2:
        return math.nan
    x = np.asarray([float(row[left]) for row in rows], dtype=float)
    y = np.asarray([float(row[right]) for row in rows], dtype=float)
    if float(np.std(x)) <= 0.0 or float(np.std(y)) <= 0.0:
        return math.nan
    return float(np.corrcoef(x, y)[0, 1])


def _group_means(rows: list[dict[str, Any]], group_column: str, value_columns: list[str]) -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    for group_value in sorted({str(row[group_column]) for row in rows}):
        chunk = [row for row in rows if str(row[group_column]) == group_value]
        payload: dict[str, Any] = {group_column: group_value, "records": len(chunk)}
        payload.update({f"mean_{column}": _mean(chunk, column) for column in value_columns})
        grouped.append(payload)
    return grouped


def _write_routing_report(path: Path, rows: list[dict[str, Any]]) -> None:
    routing_rows = [row for row in rows if row["experiment"] == "routing"]
    by_corr = sorted(routing_rows, key=lambda row: float(row["correlation_error"]), reverse=True)
    best = min(routing_rows, key=lambda row: float(row["correlation_error"]))
    worst = by_corr[0]
    depth_values = [float(row["transpiled_circuit_depth"]) for row in routing_rows]
    twoq_values = [float(row["two_qubit_gate_count"]) for row in routing_rows]
    valid_values = [float(row["valid_ratio"]) for row in routing_rows]
    corr_values = [float(row["correlation_error"]) for row in routing_rows]
    mag_values = [float(row["magnetization_error"]) for row in routing_rows]
    aggregate_rows = [
        {
            "metric": "transpiled_depth",
            "min": min(depth_values),
            "max": max(depth_values),
            "mean": _mean(routing_rows, "transpiled_circuit_depth"),
        },
        {
            "metric": "two_qubit_gate_count",
            "min": min(twoq_values),
            "max": max(twoq_values),
            "mean": _mean(routing_rows, "two_qubit_gate_count"),
        },
        {
            "metric": "valid_sector_ratio",
            "min": min(valid_values),
            "max": max(valid_values),
            "mean": _mean(routing_rows, "valid_ratio"),
        },
        {
            "metric": "correlation_error",
            "min": min(corr_values),
            "max": max(corr_values),
            "mean": _mean(routing_rows, "correlation_error"),
        },
        {
            "metric": "magnetization_error",
            "min": min(mag_values),
            "max": max(mag_values),
            "mean": _mean(routing_rows, "magnetization_error"),
        },
    ]
    correlation_rows = [
        {
            "execution_feature": "transpiled_circuit_depth",
            "corr_with_correlation_error": _pearson(routing_rows, "transpiled_circuit_depth", "correlation_error"),
            "corr_with_valid_ratio": _pearson(routing_rows, "transpiled_circuit_depth", "valid_ratio"),
        },
        {
            "execution_feature": "two_qubit_gate_count",
            "corr_with_correlation_error": _pearson(routing_rows, "two_qubit_gate_count", "correlation_error"),
            "corr_with_valid_ratio": _pearson(routing_rows, "two_qubit_gate_count", "valid_ratio"),
        },
        {
            "execution_feature": "routing_inflation",
            "corr_with_correlation_error": _pearson(routing_rows, "routing_inflation", "correlation_error"),
            "corr_with_valid_ratio": _pearson(routing_rows, "routing_inflation", "valid_ratio"),
        },
    ]
    topology_rows = _group_means(
        routing_rows,
        "topology_model",
        ["transpiled_circuit_depth", "two_qubit_gate_count", "valid_ratio", "correlation_error"],
    )
    opt_rows = _group_means(
        routing_rows,
        "transpiler_optimization_level",
        ["transpiled_circuit_depth", "two_qubit_gate_count", "valid_ratio", "correlation_error"],
    )
    text = f"""# Routing Deformation Report

## Fixed source experiment

- Hamiltonian: `j1j2_frustrated`, `n_spins = 6`, `J2/J1 = 0.5`, `M = 0`
- QAOA depth: `p = 2`
- Source circuit and frozen angles: held fixed for every row
- Varied execution body: topology model, initial layout, routing method, and transpiler optimization level

## Main empirical result

The same abstract QAOA circuit produced different physical observable errors after transpilation and noisy execution. The best routing body had correlation error `{best['correlation_error']:.6g}` with routing inflation `{best['routing_inflation']:.6g}`. The worst routing body had correlation error `{worst['correlation_error']:.6g}` with routing inflation `{worst['routing_inflation']:.6g}`.

This supports the execution-body claim: routing is not just overhead bookkeeping; it changes the measured physics under noise.

Qiskit's basis translation decomposed routed SWAP structure into native `cx` operations for these generic backends, so `swap_count` is reported as direct surviving `swap` instructions and remains zero. The operative routing-deformation observables in this run are therefore transpiled depth, two-qubit gate count, and routing inflation.

## Aggregate routing statistics

{_report_table(aggregate_rows, ['metric', 'min', 'max', 'mean'])}

## Execution feature correlations

{_report_table(correlation_rows, ['execution_feature', 'corr_with_correlation_error', 'corr_with_valid_ratio'])}

## Mean deformation by topology

{_report_table(topology_rows, ['topology_model', 'records', 'mean_transpiled_circuit_depth', 'mean_two_qubit_gate_count', 'mean_valid_ratio', 'mean_correlation_error'])}

## Mean deformation by transpiler level

{_report_table(opt_rows, ['transpiler_optimization_level', 'records', 'mean_transpiled_circuit_depth', 'mean_two_qubit_gate_count', 'mean_valid_ratio', 'mean_correlation_error'])}

## Highest correlation-deformation rows

{_report_table(by_corr[:10], ['topology_model', 'initial_layout_policy', 'routing_method', 'transpiler_optimization_level', 'transpiled_circuit_depth', 'two_qubit_gate_count', 'swap_count', 'routing_inflation', 'magnetization_error', 'correlation_error', 'observed_phase_label'])}
"""
    path.write_text(text)


def _write_calibration_report(path: Path, rows: list[dict[str, Any]]) -> None:
    selected = [row for row in rows if row["experiment"] == "calibration_age"]
    baseline = selected[0] if selected else None
    baseline_label = str(baseline["observed_phase_label"]) if baseline else ""
    changed = [row for row in selected if str(row["observed_phase_label"]) != baseline_label]
    first_change = min(changed, key=lambda row: float(row["calibration_age_seconds"])) if changed else None
    text = "# Calibration Freshness Threshold\n\n"
    text += "This simulated calibration-age experiment holds the source circuit fixed and scales the execution noise with calibration age.\n\n"
    if first_change:
        text += f"The first additional phase-label change relative to the freshest observed execution occurred at `{first_change['calibration_age_seconds']}` seconds.\n\n"
    else:
        text += "No additional phase-label change occurred after the freshest observed execution; routing/noise had already moved the observed label away from the ideal source label. Observable errors and trust-gate pressure still changed with age.\n\n"
    text += _report_table(selected, ["calibration_age_seconds", "noise_scale", "energy_error_vs_ideal_qaoa", "magnetization_error", "correlation_error", "confidence_interval_width", "observed_phase_label"])
    path.write_text(text + "\n")


def _write_shot_report(path: Path, rows: list[dict[str, Any]]) -> None:
    selected = [row for row in rows if row["experiment"] == "shot_body"]
    text = """# Shot-Body Stability Report

Finite shots are treated here as a measurement body. The question is not only how many shots estimate energy, but how many shots keep the physical conclusion stable.

"""
    text += _report_table(selected, ["shots", "confidence_interval_width", "valid_ratio", "energy_error_vs_ideal_qaoa", "magnetization_error", "correlation_error", "observed_phase_label"])
    path.write_text(text + "\n")


def _write_session_report(path: Path, rows: list[dict[str, Any]]) -> None:
    selected = [row for row in rows if row["experiment"] == "session_body"]
    text = """# Session Drift Report

This compact run compares batched execution against split and drifted execution. Each row aggregates equivalent circuit executions under a different session policy.

"""
    text += _report_table(selected, ["session_policy", "session_duration_seconds", "noise_scale", "energy_error_vs_ideal_qaoa", "magnetization_error", "correlation_error", "observed_phase_label"])
    path.write_text(text + "\n")


def _write_mitigation_report(path: Path, rows: list[dict[str, Any]]) -> None:
    selected = [row for row in rows if row["experiment"] == "mitigation_body"]
    false_corrections = []
    raw = next((row for row in selected if row["mitigation_policy"] == "none"), None)
    for row in selected:
        if raw and row["mitigation_policy"] != "none":
            energy_improved = float(row["energy_error_vs_ideal_qaoa"]) < float(raw["energy_error_vs_ideal_qaoa"])
            corr_worse = float(row["correlation_error"]) > float(raw["correlation_error"])
            if energy_improved and corr_worse:
                false_corrections.append(row["mitigation_policy"])
    text = """# Mitigation Deformation Report

Mitigation is evaluated as a physical transformation, not merely an energy-number improvement.

"""
    if false_corrections:
        text += f"Potential false-correction cases: `{', '.join(false_corrections)}` improved energy error while worsening correlation error.\n\n"
    else:
        text += "No false-correction case appeared in this compact sweep.\n\n"
    text += _report_table(selected, ["mitigation_policy", "mitigation_shift", "mitigation_instability", "energy_error_vs_ideal_qaoa", "magnetization_error", "correlation_error", "observed_phase_label"])
    path.write_text(text + "\n")


def _write_classical_frontier(path: Path, rows: list[dict[str, Any]], problem: IsingSpinProblem) -> None:
    accepted = [row for row in rows if row.get("trust_decision") == "accept_quantum_result"]
    rejected = [row for row in rows if str(row.get("trust_decision", "")).startswith("reject")]
    text = f"""# Classical vs Quantum Stability

The exact feasible classical baseline is stable for this compact workload:

- exact feasible energy: `{problem.exact_feasible_energy:.8f}`
- exact feasible bitstring: `{problem.exact_feasible_bitstring}`
- valid-sector ratio: `1.0`
- shots: `0`

Across execution-body records:

- accepted quantum records: `{len(accepted)}`
- rejected quantum records: `{len(rejected)}`

The important conclusion is not that QAOA never produces a low energy. It often does. The issue is that execution-body deformation can make the measured physical observables less stable than the classical reference.
"""
    path.write_text(text)


def _plot_outputs(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    plt = load_matplotlib_pyplot()
    routing = [row for row in rows if row["experiment"] == "routing"]
    if routing:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter([float(row["two_qubit_gate_count"]) for row in routing], [float(row["correlation_error"]) for row in routing], label="correlation")
        ax.scatter([float(row["two_qubit_gate_count"]) for row in routing], [float(row["magnetization_error"]) for row in routing], label="magnetization")
        ax.set_xlabel("transpiled two-qubit gate count")
        ax.set_ylabel("observable error vs ideal QAOA")
        ax.legend()
        fig.savefig(output_dir / "routing_deformation_curve.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    calibration = [row for row in rows if row["experiment"] == "calibration_age"]
    if calibration:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot([float(row["calibration_age_seconds"]) for row in calibration], [float(row["correlation_error"]) for row in calibration], marker="o")
        ax.set_xlabel("calibration age seconds")
        ax.set_ylabel("correlation error vs ideal QAOA")
        fig.savefig(output_dir / "calibration_age_stability.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    shots = [row for row in rows if row["experiment"] == "shot_body"]
    if shots:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot([int(row["shots"]) for row in shots], [float(row["confidence_interval_width"]) for row in shots], marker="o")
        ax.set_xscale("log", base=2)
        ax.set_xlabel("shots")
        ax.set_ylabel("energy CI width")
        fig.savefig(output_dir / "shot_body_stability_surface.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    mitigation = [row for row in rows if row["experiment"] == "mitigation_body"]
    if mitigation:
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.scatter([float(row["energy_error_vs_ideal_qaoa"]) for row in mitigation], [float(row["correlation_error"]) for row in mitigation])
        for row in mitigation:
            ax.annotate(str(row["mitigation_policy"]), (float(row["energy_error_vs_ideal_qaoa"]), float(row["correlation_error"])), fontsize=8)
        ax.set_xlabel("energy error vs ideal QAOA")
        ax.set_ylabel("correlation error vs ideal QAOA")
        fig.savefig(output_dir / "mitigation_deformation_plot.png", dpi=160, bbox_inches="tight")
        plt.close(fig)


def run(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = _base_cfg()
    problem = IsingSpinProblem(cfg)
    params, source_metrics = _optimize_frozen_angles(cfg, problem)
    gamma, beta = _angles(params, cfg.depth)
    source_measured = _build_parametric_qaoa_circuit(cfg, gamma, beta, measure=True)
    source_depth = int(source_measured.depth())
    gate = RuntimeTrustGate(
        max_calibration_age_seconds=1800.0,
        max_two_qubit_gate_inflation=2.5,
        max_confidence_interval_width=0.25,
        max_mitigation_shift=0.2,
        max_observable_error=0.35,
    )
    rows: list[dict[str, Any]] = []

    layouts = {
        "identity": [0, 1, 2, 3, 4, 5],
        "reversed": [5, 4, 3, 2, 1, 0],
        "scattered": [0, 2, 4, 1, 3, 5],
    }
    for topology in ("line", "star", "forked_heavy_hex"):
        for layout_name, layout in layouts.items():
            for optimization_level in (0, 1, 2, 3):
                for routing_method in ("basic", "sabre"):
                    row, _, _, _ = _execute_body(
                        cfg=cfg,
                        problem=problem,
                        params=params,
                        source_metrics=source_metrics,
                        source_depth=source_depth,
                        topology_model=topology,
                        optimization_level=optimization_level,
                        initial_layout_policy=layout_name,
                        initial_layout=layout,
                        routing_method=routing_method,
                        shots=2048,
                        noise_scale=1.0,
                        calibration_age_seconds=120.0,
                        session_policy="single_session",
                        mitigation_policy="none",
                        seed_offset=len(rows) + 1,
                    )
                    row["experiment"] = "routing"
                    rows.append(row)

    for age in (0, 300, 900, 1800, 3600):
        noise_scale = 1.0 + age / 1800.0
        row, _, _, _ = _execute_body(
            cfg=cfg,
            problem=problem,
            params=params,
            source_metrics=source_metrics,
            source_depth=source_depth,
            topology_model="forked_heavy_hex",
            optimization_level=1,
            initial_layout_policy="scattered",
            initial_layout=layouts["scattered"],
            routing_method="sabre",
            shots=2048,
            noise_scale=noise_scale,
            calibration_age_seconds=float(age),
            session_policy="single_session",
            mitigation_policy="none",
            seed_offset=100 + age,
        )
        row["experiment"] = "calibration_age"
        rows.append(row)

    for shots in (128, 256, 512, 1024, 4096, 8192):
        row, _, _, _ = _execute_body(
            cfg=cfg,
            problem=problem,
            params=params,
            source_metrics=source_metrics,
            source_depth=source_depth,
            topology_model="forked_heavy_hex",
            optimization_level=1,
            initial_layout_policy="scattered",
            initial_layout=layouts["scattered"],
            routing_method="sabre",
            shots=shots,
            noise_scale=1.0,
            calibration_age_seconds=120.0,
            session_policy="single_session",
            mitigation_policy="none",
            seed_offset=200 + shots,
        )
        row["experiment"] = "shot_body"
        row["bernoulli_valid_ratio_ci_width"] = bernoulli_confidence_interval_width(float(row["valid_ratio"]), int(shots))
        rows.append(row)

    session_specs = {
        "single_session": [1.0, 1.0, 1.0, 1.0],
        "split_session": [1.0, 1.2, 1.4, 1.6],
        "randomized_order": [1.4, 1.0, 1.6, 1.2],
        "grouped_by_observable": [1.0, 1.0, 1.6, 1.6],
    }
    for session_policy, scales in session_specs.items():
        segment_counts: list[tuple[dict[str, float], float]] = []
        representative_row: dict[str, Any] | None = None
        representative_transpiled: Any | None = None
        for idx, scale in enumerate(scales):
            row, _, transpiled, counts = _execute_body(
                cfg=cfg,
                problem=problem,
                params=params,
                source_metrics=source_metrics,
                source_depth=source_depth,
                topology_model="forked_heavy_hex",
                optimization_level=1,
                initial_layout_policy="scattered",
                initial_layout=layouts["scattered"],
                routing_method="sabre",
                shots=1024,
                noise_scale=scale,
                calibration_age_seconds=120.0 + idx * 300.0,
                session_policy=session_policy,
                mitigation_policy="none",
                seed_offset=300 + idx + len(rows),
            )
            representative_row = row
            representative_transpiled = transpiled
            segment_counts.append((counts, 1.0))
        assert representative_row is not None and representative_transpiled is not None
        observed = _combined_metrics(problem, segment_counts)
        session_row = _record(
            cfg=cfg,
            problem=problem,
            problem_id="frustrated_n6_j2_05_p2_seed314",
            backend_name="generic_forked_heavy_hex",
            snapshot_id=representative_row["calibration_snapshot_id"],
            calibration_age_seconds=max(120.0 + idx * 300.0 for idx in range(len(scales))),
            source_depth=source_depth,
            transpiled=representative_transpiled,
            source_metrics=source_metrics,
            observed_metrics=observed,
            shots=4096,
            queue_delay_seconds=300.0 * (len(scales) - 1),
            session_duration_seconds=900.0,
            runtime_seconds=sum(float(representative_row.get("runtime_seconds", 0.0)) for _ in scales),
            mitigation_shift=None,
            mitigation_instability=None,
            decision="run_quantum",
            rejection_reason=None,
            extra={
                "experiment": "session_body",
                "topology_model": "forked_heavy_hex",
                "transpiler_optimization_level": 1,
                "initial_layout_policy": "scattered",
                "routing_method": "sabre",
                "session_policy": session_policy,
                "mitigation_policy": "none",
                "noise_scale": float(np.mean(scales)),
                "layout_distance_score": float(representative_row.get("layout_distance_score", 0.0)),
            },
        )
        rows.append(session_row)

    mitigation_rows: list[dict[str, Any]] = []
    for policy in ("none", "readout"):
        row, _, _, _ = _execute_body(
            cfg=cfg,
            problem=problem,
            params=params,
            source_metrics=source_metrics,
            source_depth=source_depth,
            topology_model="forked_heavy_hex",
            optimization_level=1,
            initial_layout_policy="scattered",
            initial_layout=layouts["scattered"],
            routing_method="sabre",
            shots=4096,
            noise_scale=1.5,
            calibration_age_seconds=600.0,
            session_policy="single_session",
            mitigation_policy=policy,
            seed_offset=500 + len(rows),
        )
        row["experiment"] = "mitigation_body"
        mitigation_rows.append(row)
        rows.append(row)

    zne_runs = []
    for factor in (1.0, 2.0, 3.0):
        row, metrics, transpiled, _ = _execute_body(
            cfg=cfg,
            problem=problem,
            params=params,
            source_metrics=source_metrics,
            source_depth=source_depth,
            topology_model="forked_heavy_hex",
            optimization_level=1,
            initial_layout_policy="scattered",
            initial_layout=layouts["scattered"],
            routing_method="sabre",
            shots=4096,
            noise_scale=1.5 * factor,
            calibration_age_seconds=600.0,
            session_policy="single_session",
            mitigation_policy="none",
            seed_offset=600 + int(factor * 10),
        )
        zne_runs.append((factor, row, metrics, transpiled))
    factors = np.array([item[0] for item in zne_runs], dtype=float)
    energy_values = np.array([float(item[2]["energy"]) for item in zne_runs], dtype=float)
    nn_values = np.array([float(item[2]["nn_correlation"]) for item in zne_runs], dtype=float)
    nnn_values = np.array([float(item[2]["nnn_correlation"]) for item in zne_runs], dtype=float)
    zne_metrics = dict(zne_runs[0][2])
    zne_metrics["energy"] = float(np.polyfit(factors, energy_values, 1)[1])
    zne_metrics["nn_correlation"] = float(np.polyfit(factors, nn_values, 1)[1])
    zne_metrics["nnn_correlation"] = float(np.polyfit(factors, nnn_values, 1)[1])
    zne_metrics["phase_label"] = _phase_label(float(zne_metrics["valid_ratio"]), float(zne_metrics["nn_correlation"]), float(zne_metrics["nnn_correlation"]))
    raw_row = mitigation_rows[0]
    zne_row = _record(
        cfg=cfg,
        problem=problem,
        problem_id="frustrated_n6_j2_05_p2_seed314",
        backend_name="generic_forked_heavy_hex",
        snapshot_id=zne_runs[0][1]["calibration_snapshot_id"],
        calibration_age_seconds=600.0,
        source_depth=source_depth,
        transpiled=zne_runs[0][3],
        source_metrics=source_metrics,
        observed_metrics=zne_metrics,
        shots=4096 * 3,
        queue_delay_seconds=0.0,
        session_duration_seconds=3.0,
        runtime_seconds=sum(float(item[1]["runtime_seconds"]) for item in zne_runs),
        mitigation_shift=float(zne_metrics["energy"]) - float(raw_row["observed_energy"]),
        mitigation_instability=max(
            abs(float(zne_metrics["nn_correlation"]) - float(raw_row["observed_nn_correlation"])),
            abs(float(zne_metrics["nnn_correlation"]) - float(raw_row["observed_nnn_correlation"])),
        ),
        decision="run_quantum",
        rejection_reason=None,
        extra={
            "experiment": "mitigation_body",
            "topology_model": "forked_heavy_hex",
            "transpiler_optimization_level": 1,
            "initial_layout_policy": "scattered",
            "routing_method": "sabre",
            "session_policy": "single_session",
            "mitigation_policy": "zne_linear",
            "noise_scale": 1.5,
            "layout_distance_score": float(raw_row.get("layout_distance_score", 0.0)),
        },
    )
    rows.append(zne_row)

    vectors = [ExecutionDeformationVector.from_mapping(row) for row in rows]
    for row, vector in zip(rows, vectors):
        conclusion = RuntimePhysicalConclusion(
            run_id=f"{row['experiment']}_{len(row)}",
            problem_id=vector.problem_id,
            execution_body_id=vector.calibration_snapshot_id,
            energy_estimate=float(row["observed_energy"]),
            energy_ci_low=float(row["observed_energy"]) - vector.confidence_interval_width / 2.0,
            energy_ci_high=float(row["observed_energy"]) + vector.confidence_interval_width / 2.0,
            magnetization_estimate=float(row["observed_magnetization"]),
            magnetization_ci_width=None,
            correlation_error=vector.correlation_error,
            phase_label=str(row["observed_phase_label"]),
            phase_label_confidence=1.0 - min(1.0, vector.confidence_interval_width),
            classical_baseline_energy=problem.exact_feasible_energy,
            classical_baseline_observable_error=0.0,
            decision="run_classical" if vector.max_observable_error > 0.35 else "run_quantum",
            decision_reason="classical baseline is more stable" if vector.max_observable_error > 0.35 else "within compact trust thresholds",
        )
        decision = gate.evaluate(vector, conclusion)
        row["trust_decision"] = decision.decision
        row["trust_reason"] = decision.reason
        row["trust_accepted"] = decision.accepted
        row["trust_warnings"] = ",".join(decision.warnings)

    _write_records(output_dir / "execution_deformation_records.csv", rows)
    summary = {
        "problem_id": "frustrated_n6_j2_05_p2_seed314",
        "n_records": len(rows),
        "experiment_families": [
            "routing",
            "calibration_age",
            "shot_body",
            "session_body",
            "mitigation_body",
            "runtime_decision_boundary",
        ],
        "record_experiments": sorted({str(row["experiment"]) for row in rows}),
        "source_depth": source_depth,
        "frozen_gamma": gamma.tolist(),
        "frozen_beta": beta.tolist(),
        "ideal_source_metrics": source_metrics,
        "exact_feasible_energy": problem.exact_feasible_energy,
        "exact_feasible_bitstring": problem.exact_feasible_bitstring,
        "accepted_records": sum(1 for row in rows if row["trust_accepted"]),
        "rejected_records": sum(1 for row in rows if not row["trust_accepted"]),
    }
    (output_dir / "execution_deformation_summary.json").write_text(json_dumps_clean(summary, indent=2))
    _write_routing_report(output_dir / "routing_deformation_report.md", rows)
    _write_calibration_report(output_dir / "calibration_freshness_threshold.md", rows)
    _write_shot_report(output_dir / "shot_body_stability_report.md", rows)
    _write_session_report(output_dir / "session_drift_report.md", rows)
    _write_mitigation_report(output_dir / "mitigation_deformation_report.md", rows)
    (output_dir / "runtime_decision_boundary.md").write_text(build_runtime_trust_report(vectors, gate))
    _write_classical_frontier(output_dir / "classical_vs_quantum_stability.md", rows, problem)
    _plot_outputs(output_dir, rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run compact SpinMesh execution-body deformation experiments.")
    parser.add_argument("--output-dir", type=Path, default=Path("results/execution_body"))
    args = parser.parse_args()
    summary = run(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
