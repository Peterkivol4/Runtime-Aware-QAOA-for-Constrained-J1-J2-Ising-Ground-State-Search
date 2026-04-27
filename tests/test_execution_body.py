from __future__ import annotations

from datetime import datetime, timezone

import pytest

from spinmesh_runtime.execution_body import (
    REJECT_CALIBRATION_STALE,
    REJECT_CLASSICAL_DOMINATES,
    REJECT_MITIGATION_UNSTABLE,
    REJECT_ROUTING_DEFORMED,
    REJECT_SHOT_UNSTABLE,
    ExecutionBodyConfig,
    ExecutionDeformationVector,
    MitigationDeformationRecord,
    RuntimePhysicalConclusion,
    RuntimeTrustGate,
    bernoulli_confidence_interval_width,
    calibration_snapshot_hash,
    compute_calibration_age_seconds,
    count_swap_operations,
    count_two_qubit_operations,
    ensure_single_calibration_snapshot,
    layout_distance_score,
)


def _vector(**overrides: object) -> ExecutionDeformationVector:
    payload = {
        "problem_id": "frustrated_n6_j2_05",
        "backend_name": "aer_noise",
        "calibration_snapshot_id": "snapshot-a",
        "calibration_age_seconds": 60.0,
        "n_spins": 6,
        "p_layers": 2,
        "j1": 1.0,
        "j2": 0.5,
        "h": 0.0,
        "source_circuit_depth": 20,
        "transpiled_circuit_depth": 24,
        "two_qubit_gate_count": 18,
        "swap_count": 0,
        "layout_distance_score": 1.0,
        "shots": 1024,
        "queue_delay_seconds": 0.0,
        "session_duration_seconds": 4.0,
        "energy_error_vs_exact": 0.01,
        "energy_error_vs_ideal_qaoa": 0.02,
        "magnetization_error": 0.01,
        "correlation_error": 0.01,
        "structure_factor_error": None,
        "phase_label_changed": False,
        "sample_variance": 0.02,
        "confidence_interval_width": 0.05,
        "mitigation_shift": 0.01,
        "mitigation_instability": 0.01,
        "runtime_seconds": 1.0,
        "quantum_decision": "run_quantum",
        "rejection_reason": None,
    }
    payload.update(overrides)
    return ExecutionDeformationVector(**payload)


def _gate() -> RuntimeTrustGate:
    return RuntimeTrustGate(
        max_calibration_age_seconds=300.0,
        max_two_qubit_gate_inflation=2.0,
        max_confidence_interval_width=0.2,
        max_mitigation_shift=0.1,
        max_observable_error=0.2,
    )


def test_execution_body_config_requires_backend() -> None:
    with pytest.raises(ValueError, match="backend_name"):
        ExecutionBodyConfig(
            backend_name="",
            topology_model="heavy_hex",
            transpiler_optimization_level=1,
            initial_layout_policy="default",
            shots=1024,
            session_policy="single_session",
        )


def test_execution_body_config_rejects_invalid_transpiler_level() -> None:
    with pytest.raises(ValueError, match="transpiler_optimization_level"):
        ExecutionBodyConfig(
            backend_name="ibm_fez",
            topology_model="heavy_hex",
            transpiler_optimization_level=4,
            initial_layout_policy="default",
            shots=1024,
            session_policy="single_session",
        )


def test_execution_body_config_requires_shots_positive() -> None:
    with pytest.raises(ValueError, match="shots"):
        ExecutionBodyConfig(
            backend_name="aer",
            topology_model="line",
            transpiler_optimization_level=1,
            initial_layout_policy="default",
            shots=0,
            session_policy="single_session",
        )


def test_session_policy_known() -> None:
    with pytest.raises(ValueError, match="session_policy"):
        ExecutionBodyConfig(
            backend_name="aer",
            topology_model="line",
            transpiler_optimization_level=1,
            initial_layout_policy="default",
            shots=1024,
            session_policy="unknown_policy",
        )


def test_calibration_snapshot_has_hash() -> None:
    snapshot = {"backend_name": "ibm_fez", "qubits": [{"t1": 100.0, "t2": 120.0}]}
    assert calibration_snapshot_hash(snapshot) == calibration_snapshot_hash({"qubits": [{"t2": 120.0, "t1": 100.0}], "backend_name": "ibm_fez"})
    assert len(calibration_snapshot_hash(snapshot)) == 64


def test_calibration_age_computed_from_execution_time() -> None:
    calibration_time = datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc)
    execution_time = datetime(2026, 4, 25, 10, 5, 30, tzinfo=timezone.utc)
    assert compute_calibration_age_seconds(calibration_time, execution_time) == 330.0


def test_stale_calibration_triggers_rejection() -> None:
    decision = _gate().evaluate(_vector(calibration_age_seconds=600.0))
    assert decision.reason == REJECT_CALIBRATION_STALE
    assert not decision.accepted


def test_mixed_calibration_runs_not_aggregated_silently() -> None:
    records = [_vector(calibration_snapshot_id="a"), _vector(calibration_snapshot_id="b")]
    with pytest.raises(ValueError, match="mixed calibration"):
        ensure_single_calibration_snapshot(records)


def test_swap_and_two_qubit_counts_recorded_from_operations() -> None:
    operations = ["rz", "cx", "swap", "ecr", "measure"]
    assert count_two_qubit_operations(operations) == 3
    assert count_swap_operations(operations) == 1


def test_layout_policy_changes_layout_distance_score() -> None:
    edges = [(0, 1), (1, 2), (2, 3)]
    assert layout_distance_score([0, 1, 2, 3], edges) == 1.0
    assert layout_distance_score([0, 3, 1, 2], edges) > 1.0


def test_confidence_interval_width_decreases_with_shots() -> None:
    assert bernoulli_confidence_interval_width(0.5, 4096) < bernoulli_confidence_interval_width(0.5, 128)


def test_low_shot_result_can_be_rejected() -> None:
    decision = _gate().evaluate(_vector(shots=64, confidence_interval_width=0.4))
    assert decision.reason == REJECT_SHOT_UNSTABLE


def test_phase_label_requires_confidence() -> None:
    with pytest.raises(ValueError, match="phase_label_confidence"):
        RuntimePhysicalConclusion(
            run_id="run-a",
            problem_id="problem-a",
            execution_body_id="body-a",
            energy_estimate=-1.0,
            energy_ci_low=-1.1,
            energy_ci_high=-0.9,
            magnetization_estimate=0.0,
            magnetization_ci_width=0.1,
            correlation_error=0.02,
            phase_label="frustrated",
            phase_label_confidence=None,
            classical_baseline_energy=-1.0,
            classical_baseline_observable_error=0.01,
            decision="run_quantum",
            decision_reason="clean",
        )


def test_mitigation_shift_recorded_without_overwriting_raw_result() -> None:
    record = MitigationDeformationRecord(raw_energy=-1.0, mitigated_energy=-0.9, raw_observable_error=0.2, mitigated_observable_error=0.1)
    assert record.energy_shift == pytest.approx(0.1)
    assert record.as_dict()["raw_energy"] == -1.0
    assert record.as_dict()["mitigated_energy"] == -0.9


def test_large_mitigation_shift_triggers_warning() -> None:
    decision = _gate().evaluate(_vector(mitigation_shift=0.5))
    assert decision.reason == REJECT_MITIGATION_UNSTABLE


def test_runtime_trust_gate_accepts_clean_run() -> None:
    decision = _gate().evaluate(_vector())
    assert decision.accepted
    assert decision.decision == "accept_quantum_result"


def test_runtime_trust_gate_rejects_routing_deformed_run() -> None:
    decision = _gate().evaluate(_vector(transpiled_circuit_depth=80, swap_count=12))
    assert decision.reason == REJECT_ROUTING_DEFORMED


def test_runtime_trust_gate_rejects_swap_inflated_run() -> None:
    decision = _gate().evaluate(_vector(transpiled_circuit_depth=24, two_qubit_gate_count=40, swap_count=30))
    assert decision.reason == REJECT_ROUTING_DEFORMED


def test_runtime_trust_gate_rejects_classical_dominates() -> None:
    conclusion = RuntimePhysicalConclusion(
        run_id="run-a",
        problem_id="problem-a",
        execution_body_id="body-a",
        energy_estimate=-0.95,
        energy_ci_low=-1.0,
        energy_ci_high=-0.9,
        magnetization_estimate=0.0,
        magnetization_ci_width=0.1,
        correlation_error=0.3,
        phase_label="frustrated",
        phase_label_confidence=0.8,
        classical_baseline_energy=-1.0,
        classical_baseline_observable_error=0.01,
        decision="run_classical",
        decision_reason="classical baseline is more stable",
    )
    decision = _gate().evaluate(_vector(correlation_error=0.4), conclusion)
    assert decision.reason == REJECT_CLASSICAL_DOMINATES


def test_decision_reason_is_canonical() -> None:
    reasons = {
        _gate().evaluate(_vector(calibration_age_seconds=999.0)).reason,
        _gate().evaluate(_vector(transpiled_circuit_depth=99)).reason,
        _gate().evaluate(_vector(confidence_interval_width=0.99)).reason,
        _gate().evaluate(_vector(mitigation_instability=0.99)).reason,
        _gate().evaluate(_vector(quantum_decision="run_classical")).reason,
    }
    assert reasons == {
        REJECT_CALIBRATION_STALE,
        REJECT_ROUTING_DEFORMED,
        REJECT_SHOT_UNSTABLE,
        REJECT_MITIGATION_UNSTABLE,
        REJECT_CLASSICAL_DOMINATES,
    }
