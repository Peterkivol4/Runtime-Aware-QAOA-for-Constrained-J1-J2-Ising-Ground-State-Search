from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, field, fields
import os
from typing import Any, get_args, get_origin

import numpy as np

from .constants import ENV_PREFIX


SUPPORTED_LATTICE_TYPES = (
    "random_bond",
    "afm_uniform",
    "j1j2_frustrated",
    "diluted",
    "random_ferrimagnet",
)
LEGACY_LATTICE_TYPE_MAP = {
    "random": "random_bond",
    "low_corr": "afm_uniform",
    "high_corr": "j1j2_frustrated",
    "sparse": "diluted",
    "clustered": "j1j2_frustrated",
    "high_penalty": "random_ferrimagnet",
    "real_market": "j1j2_frustrated",
}
SUPPORTED_REGIMES = SUPPORTED_LATTICE_TYPES
SUPPORTED_PARAMETERIZATIONS = ("fourier", "direct")
SUPPORTED_CONSTRAINT_HANDLERS = ("remap", "penalty")
SUPPORTED_RUNTIME_MODES = ("auto", "local_proxy", "aer", "runtime_v2")
SUPPORTED_PENALTY_SCHEDULES = ("static", "annealed", "augmented_lagrangian")
SUPPORTED_TRACKERS = ("sqlite", "mlflow", "both", "none")
SUPPORTED_SIDECAR_POLICIES = ("local_only", "always", "never")
SUPPORTED_RUNTIME_EXECUTION_MODES = ("auto", "backend", "session", "batch")
SUPPORTED_BO_EPOCH_STRATEGIES = ("contextual", "warm_start_reset")


def _env_name(name: str) -> str:
    return f"{ENV_PREFIX}{name.upper()}"


def _coerce_env_value(raw: str, annotation: Any) -> Any:
    origin = get_origin(annotation)
    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    if origin is None and annotation in {str, int, float, bool}:
        if annotation is bool:
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return annotation(raw)
    if origin is tuple:
        item_type = args[0] if args else str
        return tuple(_coerce_env_value(part.strip(), item_type) for part in raw.split(",") if part.strip())
    if args and len(args) == 1:
        if raw.strip().lower() in {"", "none", "null"}:
            return None
        return _coerce_env_value(raw, args[0])
    return raw


@dataclass(init=False)
class RunDeck:
    seed: int = 42
    n_spins: int = 6
    magnetization_m: int = 0
    j1_coupling: float = 1.0
    j2_coupling: float = 0.5
    disorder_strength: float = 0.3
    h_field: float = 0.0
    lattice_type: str = "j1j2_frustrated"
    bond_dilution_prob: float = 0.0
    depth: int = 3
    fourier_modes: int = 2
    base_shots: int = 256
    cvar_alpha: float = 0.25
    bo_iters: int = 24
    sobol_init_iters: int = 8
    spsa_iters: int = 24
    random_search_iters: int = 24
    classical_bo_iters: int = 24
    classical_local_search_restarts: int = 12
    sa_steps: int = 200
    use_noise: bool = True
    use_zne: bool = True
    use_readout_mitigation: bool = True
    dynamic_shots_enabled: bool = True
    parameterization: str = "fourier"
    constraint_handling: str = "remap"
    penalty_strength: float = 2.5
    penalty_schedule: str = "annealed"
    penalty_epoch_length: int = 6
    penalty_warmup_fraction: float = 0.35
    penalty_growth_factor: float = 4.0
    penalty_max_multiplier: float = 10.0
    alm_dual_lr: float = 0.75
    bo_contextual_penalty: bool = True
    bo_epoch_strategy: str = "contextual"
    bo_reset_on_penalty_epoch: bool = False
    bo_epoch_warmstart_points: int = 2
    spsa_epoch_reset: bool = True
    spsa_epoch_step_boost: float = 1.0
    noise_level: float = 0.04
    readout_p10: float = 0.01
    readout_p01: float = 0.03
    t1_time: float = 50e3
    t2_time: float = 70e3
    gate_time: float = 100.0
    depol_error: float = 0.005
    runtime_mode: str = "auto"
    runtime_backend: str | None = None
    runtime_execution_mode: str = "auto"
    runtime_resilience_level: int = 1
    runtime_probe_readout_each_eval: bool = True
    runtime_probe_shots: int = 64
    runtime_probe_frequency: int = 10
    runtime_probe_policy: str = "local_only"
    runtime_calibration_snapshot: str | None = None
    runtime_estimated_total_shots: int | None = None
    runtime_auto_batch_shot_threshold: int = 50000
    runtime_retry_attempts: int = 3
    runtime_retry_backoff_seconds: float = 2.0
    runtime_checkpoint_enabled: bool = True
    runtime_resume_enabled: bool = True
    runtime_checkpoint_every: int = 1
    runtime_run_label: str | None = None
    shot_governor_enabled: bool = True
    shot_governor_budget_multiplier: float = 1.25
    shot_governor_patience: int = 4
    shot_governor_min_improvement: float = 1e-3
    shot_governor_escalation: float = 1.5
    shot_governor_min_shots: int = 32
    shot_governor_max_shots: int = 2048
    shot_governor_max_cumulative_shots: int | None = None
    decision_runtime_weight: float = 0.5
    decision_shot_weight: float = 0.5
    use_twirling: bool = False
    use_dynamical_decoupling: bool = False
    study_num_seeds: int = 20
    study_n_spins: tuple[int, ...] = (6,)
    study_budget_ratio: float | None = 0.5
    study_depths: tuple[int, ...] = (1, 2, 3, 4)
    study_shot_budgets: tuple[int, ...] = (128, 256, 512)
    study_noise_levels: tuple[float, ...] = (0.0, 0.02, 0.05, 0.08)
    study_j2_ratios: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)
    study_disorder_levels: tuple[float, ...] = (0.0, 0.1, 0.3, 0.5)
    epsilon_success: float = 0.05
    tracker_backend: str = "sqlite"
    tracker_uri: str | None = None
    tracker_experiment_name: str = "runtime_aware_qaoa"
    output_prefix: str = "runtime_aware_qaoa_ising"

    def __init__(self, **kwargs: Any):
        payload = dict(kwargs)
        legacy_n_assets = payload.pop("n_assets", None)
        if legacy_n_assets is not None and "n_spins" not in payload:
            payload["n_spins"] = legacy_n_assets
        legacy_regime = payload.pop("regime", None)
        if legacy_regime is not None and "lattice_type" not in payload:
            payload["lattice_type"] = legacy_regime
        legacy_study_n_assets = payload.pop("study_n_assets", None)
        if legacy_study_n_assets is not None and "study_n_spins" not in payload:
            payload["study_n_spins"] = legacy_study_n_assets
        legacy_study_regimes = payload.pop("study_regimes", None)
        if legacy_study_regimes is not None and "lattice_type" not in payload:
            study_regimes = tuple(legacy_study_regimes)
            if study_regimes:
                payload["lattice_type"] = study_regimes[0]
        legacy_budget = payload.pop("budget", None)
        legacy_budget_ratio = payload.pop("budget_ratio", None)
        payload.pop("risk_aversion", None)
        payload.pop("market_data_csv", None)
        payload.pop("market_date_column", None)
        payload.pop("market_window", None)
        payload.pop("market_window_index", None)
        if "lattice_type" in payload:
            payload["lattice_type"] = LEGACY_LATTICE_TYPE_MAP.get(str(payload["lattice_type"]), payload["lattice_type"])
        field_map = {item.name: item for item in fields(type(self))}
        if legacy_budget is not None and "magnetization_m" not in payload:
            n_spins = int(payload.get("n_spins", field_map["n_spins"].default))
            payload["magnetization_m"] = int(2 * int(legacy_budget) - n_spins)
        if legacy_budget_ratio is not None and "study_budget_ratio" not in payload:
            payload["study_budget_ratio"] = legacy_budget_ratio
        unknown = sorted(key for key in payload if key not in field_map)
        if unknown:
            joined = ", ".join(unknown)
            raise TypeError(f"RunDeck got unexpected keyword arguments: {joined}")
        for item in fields(type(self)):
            if item.name in payload:
                value = payload[item.name]
            elif item.default is not MISSING:
                value = item.default
            elif item.default_factory is not MISSING:  # type: ignore[attr-defined]
                value = item.default_factory()
            else:  # pragma: no cover - dataclass fields all have defaults
                raise TypeError(f"Missing required field: {item.name}")
            setattr(self, item.name, value)

    @classmethod
    def from_environment(cls, overrides: dict[str, Any] | None = None, *, validate: bool = True) -> "RunDeck":
        payload: dict[str, Any] = {}
        for item in fields(cls):
            raw = os.getenv(_env_name(item.name))
            if raw is None:
                continue
            payload[item.name] = _coerce_env_value(raw, item.type)
        if overrides:
            for key, value in overrides.items():
                if value is None:
                    continue
                payload[key] = value
        cfg = cls(**payload)
        if validate:
            cfg.validate()
        return cfg

    @property
    def n_assets(self) -> int:
        return self.n_spins

    @property
    def budget(self) -> int:
        return (self.magnetization_m + self.n_spins) // 2

    @property
    def magnetization_sector_k(self) -> int:
        return self.budget

    @property
    def regime(self) -> str:
        return self.lattice_type

    @property
    def study_n_assets(self) -> tuple[int, ...]:
        return self.study_n_spins

    @property
    def study_regimes(self) -> tuple[str, ...]:
        return (self.lattice_type,)

    @property
    def j2_ratio(self) -> float:
        if abs(self.j1_coupling) <= 1e-12:
            return 0.0
        return float(self.j2_coupling / self.j1_coupling)

    def validate(self) -> None:
        if self.n_spins <= 1:
            raise ValueError("n_spins must be greater than 1.")
        if not (0 <= self.budget <= self.n_spins):
            raise ValueError("derived budget must lie in [0, n_spins].")
        if abs(self.magnetization_m) > self.n_spins:
            raise ValueError("magnetization_m must lie in [-n_spins, n_spins].")
        if (self.magnetization_m + self.n_spins) % 2 != 0:
            raise ValueError("magnetization_m must have the same parity as n_spins.")
        if self.depth <= 0:
            raise ValueError("depth must be positive.")
        if self.fourier_modes <= 0:
            raise ValueError("fourier_modes must be positive.")
        if self.base_shots <= 0:
            raise ValueError("base_shots must be positive.")
        if self.bo_iters <= 0 or self.sobol_init_iters <= 0:
            raise ValueError("bo_iters and sobol_init_iters must be positive.")
        if self.spsa_iters <= 0 or self.random_search_iters <= 0 or self.classical_bo_iters <= 0:
            raise ValueError("all optimizer iteration counts must be positive.")
        if not (0.0 < self.cvar_alpha <= 1.0):
            raise ValueError("cvar_alpha must lie in (0, 1].")
        if self.parameterization not in SUPPORTED_PARAMETERIZATIONS:
            raise ValueError(f"parameterization must be one of {SUPPORTED_PARAMETERIZATIONS}.")
        if self.constraint_handling not in SUPPORTED_CONSTRAINT_HANDLERS:
            raise ValueError(f"constraint_handling must be one of {SUPPORTED_CONSTRAINT_HANDLERS}.")
        if self.lattice_type not in SUPPORTED_LATTICE_TYPES:
            raise ValueError(f"lattice_type must be one of {SUPPORTED_LATTICE_TYPES}.")
        if self.runtime_mode not in SUPPORTED_RUNTIME_MODES:
            raise ValueError(f"runtime_mode must be one of {SUPPORTED_RUNTIME_MODES}.")
        if self.penalty_schedule not in SUPPORTED_PENALTY_SCHEDULES:
            raise ValueError(f"penalty_schedule must be one of {SUPPORTED_PENALTY_SCHEDULES}.")
        if self.tracker_backend not in SUPPORTED_TRACKERS:
            raise ValueError(f"tracker_backend must be one of {SUPPORTED_TRACKERS}.")
        if self.runtime_probe_policy not in SUPPORTED_SIDECAR_POLICIES:
            raise ValueError(f"runtime_probe_policy must be one of {SUPPORTED_SIDECAR_POLICIES}.")
        if self.runtime_execution_mode not in SUPPORTED_RUNTIME_EXECUTION_MODES:
            raise ValueError(f"runtime_execution_mode must be one of {SUPPORTED_RUNTIME_EXECUTION_MODES}.")
        if self.bo_epoch_strategy not in SUPPORTED_BO_EPOCH_STRATEGIES:
            raise ValueError(f"bo_epoch_strategy must be one of {SUPPORTED_BO_EPOCH_STRATEGIES}.")
        if self.study_num_seeds <= 0:
            raise ValueError("study_num_seeds must be positive.")
        if any(depth <= 0 for depth in self.study_depths):
            raise ValueError("study_depths must all be positive.")
        if any(shots <= 0 for shots in self.study_shot_budgets):
            raise ValueError("study_shot_budgets must all be positive.")
        if any(level < 0.0 for level in self.study_noise_levels):
            raise ValueError("study_noise_levels must be non-negative.")
        if any(n_spins <= 1 for n_spins in self.study_n_spins):
            raise ValueError("study_n_spins must all be greater than 1.")
        if self.study_budget_ratio is not None and not (0.0 < self.study_budget_ratio <= 1.0):
            raise ValueError("study_budget_ratio must lie in (0, 1].")
        if any(ratio < 0.0 for ratio in self.study_j2_ratios):
            raise ValueError("study_j2_ratios must be non-negative.")
        if any(level < 0.0 for level in self.study_disorder_levels):
            raise ValueError("study_disorder_levels must be non-negative.")
        if not (0.0 <= self.penalty_warmup_fraction < 1.0):
            raise ValueError("penalty_warmup_fraction must lie in [0, 1).")
        if self.penalty_growth_factor < 1.0:
            raise ValueError("penalty_growth_factor must be at least 1.0.")
        if self.penalty_max_multiplier < 1.0:
            raise ValueError("penalty_max_multiplier must be at least 1.0.")
        if self.penalty_epoch_length <= 0:
            raise ValueError("penalty_epoch_length must be positive.")
        if self.runtime_probe_shots <= 0:
            raise ValueError("runtime_probe_shots must be positive.")
        if self.runtime_probe_frequency <= 0:
            raise ValueError("runtime_probe_frequency must be positive.")
        if self.runtime_resilience_level < 0:
            raise ValueError("runtime_resilience_level must be non-negative.")
        if self.bo_epoch_warmstart_points < 0:
            raise ValueError("bo_epoch_warmstart_points must be non-negative.")
        if self.spsa_epoch_step_boost <= 0.0:
            raise ValueError("spsa_epoch_step_boost must be positive.")
        if self.runtime_auto_batch_shot_threshold <= 0:
            raise ValueError("runtime_auto_batch_shot_threshold must be positive.")
        if self.runtime_retry_attempts <= 0:
            raise ValueError("runtime_retry_attempts must be positive.")
        if self.runtime_retry_backoff_seconds < 0.0:
            raise ValueError("runtime_retry_backoff_seconds must be non-negative.")
        if self.runtime_checkpoint_every <= 0:
            raise ValueError("runtime_checkpoint_every must be positive.")
        if self.runtime_estimated_total_shots is not None and self.runtime_estimated_total_shots < 0:
            raise ValueError("runtime_estimated_total_shots must be non-negative when provided.")
        if self.shot_governor_budget_multiplier < 1.0:
            raise ValueError("shot_governor_budget_multiplier must be at least 1.0.")
        if self.shot_governor_patience <= 0:
            raise ValueError("shot_governor_patience must be positive.")
        if self.shot_governor_min_improvement < 0.0:
            raise ValueError("shot_governor_min_improvement must be non-negative.")
        if self.shot_governor_escalation < 1.0:
            raise ValueError("shot_governor_escalation must be at least 1.0.")
        if self.shot_governor_min_shots <= 0 or self.shot_governor_max_shots < self.shot_governor_min_shots:
            raise ValueError("shot governor shot bounds are invalid.")
        if self.shot_governor_max_cumulative_shots is not None and self.shot_governor_max_cumulative_shots <= 0:
            raise ValueError("shot_governor_max_cumulative_shots must be positive when provided.")
        if self.decision_runtime_weight < 0.0 or self.decision_shot_weight < 0.0:
            raise ValueError("decision weights must be non-negative.")

    @property
    def dynamic_shots(self) -> int:
        if not self.dynamic_shots_enabled:
            return self.base_shots
        return max(1, int(np.ceil(self.base_shots / self.cvar_alpha)))

    def copy_with(self, **updates: Any) -> "RunDeck":
        payload = asdict(self)
        payload.update(updates)
        return RunDeck(**payload)


@dataclass
class ConstraintPenaltyState:
    linear_strength: float = 0.0
    quadratic_strength: float = 0.0
    schedule: str = "static"
    iteration: int = 0
    epoch: int = 0

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "linear_strength": float(self.linear_strength),
            "quadratic_strength": float(self.quadratic_strength),
            "schedule": self.schedule,
            "iteration": int(self.iteration),
            "epoch": int(self.epoch),
        }


@dataclass
class TailBatch:
    cvar: float
    valid_ratio: float
    variance: float
    feasible_best: float
    raw_best: float
    total_shots: int
    backend: str


@dataclass
class MeasurementOutcome:
    counts: dict[str, float]
    best_bitstring: str
    valid_ratio: float
    feasible_best: float
    raw_best: float
    total_shots: int
    backend: str
    success_probability: float = 0.0


@dataclass
class TrialResult:
    method: str
    family: str
    regime: str
    seed: int
    n_assets: int
    budget: int
    depth: int
    noise_level: float
    shot_budget: int
    parameterization: str
    mitigation_label: str
    constraint_handling: str
    best_energy: float
    exact_energy: float
    approximation_gap: float
    approximation_ratio: float
    success: bool
    valid_ratio: float
    measurement_success_probability: float
    runtime_seconds: float
    evaluations: int
    objective_calls: int
    total_shots: int
    sampler_calls: int = 0
    primitive_calls: int = 0
    final_readout_shots: int = 0
    optimization_best_energy: float | None = None
    final_readout_energy: float | None = None
    final_readout_valid_ratio: float | None = None
    final_readout_raw_best: float | None = None
    final_bitstring: str | None = None
    best_params: list[float] = field(default_factory=list)
    transpilation_metadata: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, float]] = field(default_factory=list)
    j2_ratio: float | None = None
    disorder_strength: float | None = None
    frustration_index: float | None = None
    magnetization_m: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "SUPPORTED_LATTICE_TYPES",
    "SUPPORTED_REGIMES",
    "SUPPORTED_PARAMETERIZATIONS",
    "SUPPORTED_CONSTRAINT_HANDLERS",
    "SUPPORTED_RUNTIME_MODES",
    "SUPPORTED_PENALTY_SCHEDULES",
    "SUPPORTED_TRACKERS",
    "SUPPORTED_SIDECAR_POLICIES",
    "SUPPORTED_RUNTIME_EXECUTION_MODES",
    "SUPPORTED_BO_EPOCH_STRATEGIES",
    "RunDeck",
    "ConstraintPenaltyState",
    "TailBatch",
    "MeasurementOutcome",
    "TrialResult",
]
