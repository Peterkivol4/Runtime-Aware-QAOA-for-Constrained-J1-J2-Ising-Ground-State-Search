from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


VALID_SESSION_POLICIES = (
    "single_session",
    "split_session",
    "randomized_order",
    "grouped_by_observable",
    "simulated_drift",
    "local_proxy",
)

ACCEPT_QUANTUM_RESULT = "accept_quantum_result"
ACCEPT_WITH_WARNING = "accept_with_warning"
REJECT_CALIBRATION_STALE = "runtime.reject.calibration_stale"
REJECT_ROUTING_DEFORMED = "runtime.reject.routing_deformed"
REJECT_SHOT_UNSTABLE = "runtime.reject.shot_unstable"
REJECT_MITIGATION_UNSTABLE = "runtime.reject.mitigation_unstable"
REJECT_CLASSICAL_DOMINATES = "runtime.reject.classical_dominates"


@dataclass(slots=True)
class ExecutionBodyConfig:
    backend_name: str
    topology_model: str
    transpiler_optimization_level: int
    initial_layout_policy: str
    shots: int
    session_policy: str
    queue_delay_seconds: float | None = None
    calibration_snapshot_id: str | None = None
    calibration_age_seconds: float | None = None
    mitigation_policy: str = "none"
    measurement_grouping_policy: str = "default"
    seed: int | None = None

    def __post_init__(self) -> None:
        if not str(self.backend_name).strip():
            raise ValueError("backend_name is required for execution-body records.")
        if self.transpiler_optimization_level not in {0, 1, 2, 3}:
            raise ValueError("transpiler_optimization_level must be one of 0, 1, 2, 3.")
        if self.shots <= 0:
            raise ValueError("shots must be positive.")
        if self.session_policy not in VALID_SESSION_POLICIES:
            raise ValueError(f"session_policy must be one of {VALID_SESSION_POLICIES}.")
        if self.queue_delay_seconds is not None and self.queue_delay_seconds < 0.0:
            raise ValueError("queue_delay_seconds must be non-negative when provided.")
        if self.calibration_age_seconds is not None and self.calibration_age_seconds < 0.0:
            raise ValueError("calibration_age_seconds must be non-negative when provided.")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionDeformationVector:
    problem_id: str
    backend_name: str
    calibration_snapshot_id: str
    calibration_age_seconds: float
    n_spins: int
    p_layers: int
    j1: float
    j2: float
    h: float
    source_circuit_depth: int
    transpiled_circuit_depth: int
    two_qubit_gate_count: int
    swap_count: int
    layout_distance_score: float
    shots: int
    queue_delay_seconds: float
    session_duration_seconds: float
    energy_error_vs_exact: float | None
    energy_error_vs_ideal_qaoa: float | None
    magnetization_error: float | None
    correlation_error: float | None
    structure_factor_error: float | None
    phase_label_changed: bool | None
    sample_variance: float
    confidence_interval_width: float
    mitigation_shift: float | None
    mitigation_instability: float | None
    runtime_seconds: float
    quantum_decision: str
    rejection_reason: str | None

    def __post_init__(self) -> None:
        if not self.problem_id:
            raise ValueError("problem_id is required.")
        if not self.backend_name:
            raise ValueError("backend_name is required.")
        if self.n_spins <= 0:
            raise ValueError("n_spins must be positive.")
        if self.p_layers <= 0:
            raise ValueError("p_layers must be positive.")
        if self.source_circuit_depth < 0 or self.transpiled_circuit_depth < 0:
            raise ValueError("circuit depths must be non-negative.")
        if self.two_qubit_gate_count < 0 or self.swap_count < 0:
            raise ValueError("gate counts must be non-negative.")
        if self.shots <= 0:
            raise ValueError("shots must be positive.")
        for name in ("calibration_age_seconds", "queue_delay_seconds", "session_duration_seconds", "sample_variance", "confidence_interval_width", "runtime_seconds"):
            value = float(getattr(self, name))
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative.")

    @property
    def depth_inflation(self) -> float:
        if self.source_circuit_depth == 0:
            return math.inf if self.transpiled_circuit_depth > 0 else 1.0
        return float(self.transpiled_circuit_depth / self.source_circuit_depth)

    @property
    def routing_inflation(self) -> float:
        non_swap_two_qubit = max(1, self.two_qubit_gate_count - self.swap_count)
        two_qubit_inflation = float(self.two_qubit_gate_count / non_swap_two_qubit)
        return max(self.depth_inflation, two_qubit_inflation)

    @property
    def max_observable_error(self) -> float:
        values = [
            self.energy_error_vs_exact,
            self.energy_error_vs_ideal_qaoa,
            self.magnetization_error,
            self.correlation_error,
            self.structure_factor_error,
        ]
        finite = [abs(float(value)) for value in values if value is not None and math.isfinite(float(value))]
        return max(finite) if finite else 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> "ExecutionDeformationVector":
        return cls(
            problem_id=str(row["problem_id"]),
            backend_name=str(row["backend_name"]),
            calibration_snapshot_id=str(row.get("calibration_snapshot_id") or ""),
            calibration_age_seconds=_float(row.get("calibration_age_seconds"), 0.0),
            n_spins=int(row["n_spins"]),
            p_layers=int(row["p_layers"]),
            j1=_float(row.get("j1"), 0.0),
            j2=_float(row.get("j2"), 0.0),
            h=_float(row.get("h"), 0.0),
            source_circuit_depth=int(row.get("source_circuit_depth") or 0),
            transpiled_circuit_depth=int(row.get("transpiled_circuit_depth") or 0),
            two_qubit_gate_count=int(row.get("two_qubit_gate_count") or 0),
            swap_count=int(row.get("swap_count") or 0),
            layout_distance_score=_float(row.get("layout_distance_score"), 0.0),
            shots=int(row.get("shots") or 1),
            queue_delay_seconds=_float(row.get("queue_delay_seconds"), 0.0),
            session_duration_seconds=_float(row.get("session_duration_seconds"), 0.0),
            energy_error_vs_exact=_optional_float(row.get("energy_error_vs_exact")),
            energy_error_vs_ideal_qaoa=_optional_float(row.get("energy_error_vs_ideal_qaoa")),
            magnetization_error=_optional_float(row.get("magnetization_error")),
            correlation_error=_optional_float(row.get("correlation_error")),
            structure_factor_error=_optional_float(row.get("structure_factor_error")),
            phase_label_changed=_optional_bool(row.get("phase_label_changed")),
            sample_variance=_float(row.get("sample_variance"), 0.0),
            confidence_interval_width=_float(row.get("confidence_interval_width"), 0.0),
            mitigation_shift=_optional_float(row.get("mitigation_shift")),
            mitigation_instability=_optional_float(row.get("mitigation_instability")),
            runtime_seconds=_float(row.get("runtime_seconds"), 0.0),
            quantum_decision=str(row.get("quantum_decision") or ""),
            rejection_reason=str(row["rejection_reason"]) if row.get("rejection_reason") else None,
        )


@dataclass(slots=True)
class RuntimePhysicalConclusion:
    run_id: str
    problem_id: str
    execution_body_id: str
    energy_estimate: float
    energy_ci_low: float
    energy_ci_high: float
    magnetization_estimate: float | None
    magnetization_ci_width: float | None
    correlation_error: float | None
    phase_label: str | None
    phase_label_confidence: float | None
    classical_baseline_energy: float | None
    classical_baseline_observable_error: float | None
    decision: str
    decision_reason: str

    def __post_init__(self) -> None:
        if self.energy_ci_low > self.energy_ci_high:
            raise ValueError("energy_ci_low must be less than or equal to energy_ci_high.")
        if self.phase_label is not None and self.phase_label_confidence is None:
            raise ValueError("phase_label requires phase_label_confidence.")
        if self.phase_label_confidence is not None and not (0.0 <= self.phase_label_confidence <= 1.0):
            raise ValueError("phase_label_confidence must lie in [0, 1].")
        if self.magnetization_ci_width is not None and self.magnetization_ci_width < 0.0:
            raise ValueError("magnetization_ci_width must be non-negative.")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeTrustDecision:
    decision: str
    reason: str
    accepted: bool
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeTrustGate:
    max_calibration_age_seconds: float
    max_two_qubit_gate_inflation: float
    max_confidence_interval_width: float
    max_mitigation_shift: float
    max_observable_error: float
    require_classical_baseline: bool = True

    def __post_init__(self) -> None:
        for name in (
            "max_calibration_age_seconds",
            "max_two_qubit_gate_inflation",
            "max_confidence_interval_width",
            "max_mitigation_shift",
            "max_observable_error",
        ):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must be non-negative.")

    def evaluate(
        self,
        vector: ExecutionDeformationVector,
        conclusion: RuntimePhysicalConclusion | None = None,
    ) -> RuntimeTrustDecision:
        if vector.calibration_age_seconds > self.max_calibration_age_seconds:
            return RuntimeTrustDecision("reject_calibration_stale", REJECT_CALIBRATION_STALE, False)
        if vector.routing_inflation > self.max_two_qubit_gate_inflation:
            return RuntimeTrustDecision("reject_routing_deformed", REJECT_ROUTING_DEFORMED, False)
        if vector.confidence_interval_width > self.max_confidence_interval_width:
            return RuntimeTrustDecision("reject_shot_unstable", REJECT_SHOT_UNSTABLE, False)

        mitigation_values = [vector.mitigation_shift, vector.mitigation_instability]
        if any(value is not None and abs(float(value)) > self.max_mitigation_shift for value in mitigation_values):
            return RuntimeTrustDecision("reject_mitigation_unstable", REJECT_MITIGATION_UNSTABLE, False)

        classical_dominates = False
        if conclusion is not None:
            classical_dominates = conclusion.decision in {"run_classical", "reject_classical_dominates"}
            if (
                self.require_classical_baseline
                and conclusion.classical_baseline_observable_error is not None
                and vector.max_observable_error > self.max_observable_error
                and conclusion.classical_baseline_observable_error <= self.max_observable_error
            ):
                classical_dominates = True
        if vector.quantum_decision in {"run_classical", "reject_classical_dominates"}:
            classical_dominates = True
        if classical_dominates:
            return RuntimeTrustDecision("reject_classical_dominates", REJECT_CLASSICAL_DOMINATES, False)

        warnings: list[str] = []
        if vector.swap_count > 0:
            warnings.append("runtime.warn.routing_swaps_present")
        if vector.max_observable_error > self.max_observable_error:
            warnings.append("runtime.warn.observable_error_high")
        if warnings:
            return RuntimeTrustDecision(ACCEPT_WITH_WARNING, "runtime.accept.warning", True, tuple(warnings))
        return RuntimeTrustDecision(ACCEPT_QUANTUM_RESULT, "runtime.accept.clean", True)


@dataclass(slots=True)
class MitigationDeformationRecord:
    raw_energy: float
    mitigated_energy: float
    raw_observable_error: float | None = None
    mitigated_observable_error: float | None = None

    @property
    def energy_shift(self) -> float:
        return float(self.mitigated_energy - self.raw_energy)

    @property
    def observable_shift(self) -> float | None:
        if self.raw_observable_error is None or self.mitigated_observable_error is None:
            return None
        return float(self.mitigated_observable_error - self.raw_observable_error)

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_energy": self.raw_energy,
            "mitigated_energy": self.mitigated_energy,
            "raw_observable_error": self.raw_observable_error,
            "mitigated_observable_error": self.mitigated_observable_error,
            "energy_shift": self.energy_shift,
            "observable_shift": self.observable_shift,
        }


def calibration_snapshot_hash(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_calibration_age_seconds(calibration_time: datetime | str | float | int, execution_time: datetime | str | float | int) -> float:
    calibration_dt = _to_datetime(calibration_time)
    execution_dt = _to_datetime(execution_time)
    return max(0.0, float((execution_dt - calibration_dt).total_seconds()))


def group_by_calibration_snapshot(records: Iterable[ExecutionDeformationVector]) -> dict[str, list[ExecutionDeformationVector]]:
    grouped: dict[str, list[ExecutionDeformationVector]] = {}
    for record in records:
        grouped.setdefault(record.calibration_snapshot_id, []).append(record)
    return grouped


def ensure_single_calibration_snapshot(records: Iterable[ExecutionDeformationVector]) -> str:
    grouped = group_by_calibration_snapshot(records)
    if len(grouped) != 1:
        ids = ", ".join(sorted(grouped)) or "<none>"
        raise ValueError(f"Cannot aggregate mixed calibration snapshots silently: {ids}")
    return next(iter(grouped))


def bernoulli_confidence_interval_width(probability: float, shots: int, *, z_score: float = 1.96) -> float:
    if shots <= 0:
        raise ValueError("shots must be positive.")
    p = min(1.0, max(0.0, float(probability)))
    return float(2.0 * z_score * math.sqrt((p * (1.0 - p)) / shots))


def layout_distance_score(initial_layout: Iterable[int], coupling_edges: Iterable[tuple[int, int]]) -> float:
    layout = list(initial_layout)
    if len(layout) <= 1:
        return 0.0
    graph: dict[int, set[int]] = {}
    for left, right in coupling_edges:
        graph.setdefault(int(left), set()).add(int(right))
        graph.setdefault(int(right), set()).add(int(left))
    distances = []
    for index in range(len(layout) - 1):
        distance = _shortest_path_length(graph, int(layout[index]), int(layout[index + 1]))
        distances.append(distance)
    if any(math.isinf(distance) for distance in distances):
        return math.inf
    return float(sum(distances) / len(distances))


def count_two_qubit_operations(operation_names: Iterable[str]) -> int:
    two_qubit_names = {"cx", "cz", "ecr", "swap", "iswap", "rxx", "ryy", "rzz"}
    return sum(1 for name in operation_names if str(name).lower() in two_qubit_names)


def count_swap_operations(operation_names: Iterable[str]) -> int:
    return sum(1 for name in operation_names if str(name).lower() == "swap")


def load_execution_deformation_csv(path: str | Path) -> list[ExecutionDeformationVector]:
    with Path(path).open(newline="") as handle:
        return [ExecutionDeformationVector.from_mapping(row) for row in csv.DictReader(handle)]


def build_runtime_trust_report(records: Iterable[ExecutionDeformationVector], gate: RuntimeTrustGate) -> str:
    rows = list(records)
    decisions = [gate.evaluate(row) for row in rows]
    accepted = sum(1 for decision in decisions if decision.accepted)
    lines = [
        "# Runtime Decision Boundary",
        "",
        f"- records: `{len(rows)}`",
        f"- accepted: `{accepted}`",
        f"- rejected: `{len(rows) - accepted}`",
        "",
        "| problem_id | backend | decision | reason | calibration_age_s | routing_inflation | ci_width |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row, decision in zip(rows, decisions):
        lines.append(
            "| "
            f"{row.problem_id} | {row.backend_name} | {decision.decision} | {decision.reason} | "
            f"{row.calibration_age_seconds:.3f} | {row.routing_inflation:.3f} | {row.confidence_interval_width:.6f} |"
        )
    lines.append("")
    lines.append("Quantum results are accepted only when the execution body preserves enough physical interpretability under the configured trust gate.")
    return "\n".join(lines) + "\n"


def _float(value: Any, default: float) -> float:
    if value in {None, ""}:
        return float(default)
    return float(value)


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _optional_bool(value: Any) -> bool | None:
    if value in {None, ""}:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _to_datetime(value: datetime | str | float | int) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (float, int)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _shortest_path_length(graph: dict[int, set[int]], start: int, goal: int) -> float:
    if start == goal:
        return 0.0
    frontier = [(start, 0)]
    seen = {start}
    while frontier:
        node, distance = frontier.pop(0)
        for neighbor in graph.get(node, set()):
            if neighbor == goal:
                return float(distance + 1)
            if neighbor not in seen:
                seen.add(neighbor)
                frontier.append((neighbor, distance + 1))
    return math.inf


__all__ = [
    "VALID_SESSION_POLICIES",
    "ACCEPT_QUANTUM_RESULT",
    "ACCEPT_WITH_WARNING",
    "REJECT_CALIBRATION_STALE",
    "REJECT_ROUTING_DEFORMED",
    "REJECT_SHOT_UNSTABLE",
    "REJECT_MITIGATION_UNSTABLE",
    "REJECT_CLASSICAL_DOMINATES",
    "ExecutionBodyConfig",
    "ExecutionDeformationVector",
    "RuntimePhysicalConclusion",
    "RuntimeTrustDecision",
    "RuntimeTrustGate",
    "MitigationDeformationRecord",
    "calibration_snapshot_hash",
    "compute_calibration_age_seconds",
    "group_by_calibration_snapshot",
    "ensure_single_calibration_snapshot",
    "bernoulli_confidence_interval_width",
    "layout_distance_score",
    "count_two_qubit_operations",
    "count_swap_operations",
    "load_execution_deformation_csv",
    "build_runtime_trust_report",
]
