from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import (
    RunDeck,
    SUPPORTED_BO_EPOCH_STRATEGIES,
    SUPPORTED_CONSTRAINT_HANDLERS,
    SUPPORTED_LATTICE_TYPES,
    SUPPORTED_PARAMETERIZATIONS,
    SUPPORTED_RUNTIME_EXECUTION_MODES,
    SUPPORTED_RUNTIME_MODES,
    SUPPORTED_SIDECAR_POLICIES,
    SUPPORTED_TRACKERS,
)
from .execution_body import RuntimeTrustGate, build_runtime_trust_report, load_execution_deformation_csv
from .live_certification import run_live_certification_check, save_certification_report
from .pipeline import run_benchmark_study, run_decision, run_single_benchmark, run_smoke_test
from .tracking import json_dumps_clean, sanitize_json_payload


def build_parser() -> argparse.ArgumentParser:
    defaults = RunDeck.from_environment(validate=False)
    parser = argparse.ArgumentParser(description="SpinMesh Runtime studies execution-body deformation in constrained J1-J2 QAOA.")
    parser.add_argument("--mode", type=str, default="study", help="One of: smoke, single, study, decision, live_cert, runtime_trust_report.")
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--n-spins", dest="n_spins", type=int, default=defaults.n_spins)
    parser.add_argument("--magnetization-m", type=int, default=defaults.magnetization_m)
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument("--j1-coupling", type=float, default=defaults.j1_coupling)
    parser.add_argument("--j2-coupling", type=float, default=defaults.j2_coupling)
    parser.add_argument("--disorder-strength", type=float, default=defaults.disorder_strength)
    parser.add_argument("--h-field", type=float, default=defaults.h_field)
    parser.add_argument("--bond-dilution-prob", type=float, default=defaults.bond_dilution_prob)
    parser.add_argument("--lattice-type", dest="lattice_type", choices=SUPPORTED_LATTICE_TYPES, default=defaults.lattice_type)
    parser.add_argument("--regime", dest="lattice_type", choices=SUPPORTED_LATTICE_TYPES, help=argparse.SUPPRESS)
    parser.add_argument("--depth", type=int, default=defaults.depth)
    parser.add_argument("--fourier-modes", type=int, default=defaults.fourier_modes)
    parser.add_argument("--base-shots", type=int, default=defaults.base_shots)
    parser.add_argument("--cvar-alpha", type=float, default=defaults.cvar_alpha)
    parser.add_argument("--bo-iters", type=int, default=defaults.bo_iters)
    parser.add_argument("--sobol-init-iters", type=int, default=defaults.sobol_init_iters)
    parser.add_argument("--spsa-iters", type=int, default=defaults.spsa_iters)
    parser.add_argument("--random-search-iters", type=int, default=defaults.random_search_iters)
    parser.add_argument("--classical-bo-iters", type=int, default=defaults.classical_bo_iters)
    parser.add_argument("--parameterization", choices=SUPPORTED_PARAMETERIZATIONS, default=defaults.parameterization)
    parser.add_argument("--constraint-handling", choices=SUPPORTED_CONSTRAINT_HANDLERS, default=defaults.constraint_handling)
    parser.add_argument("--runtime-mode", choices=SUPPORTED_RUNTIME_MODES, default=defaults.runtime_mode)
    parser.add_argument("--runtime-backend", type=str, default=defaults.runtime_backend)
    parser.add_argument("--runtime-execution-mode", choices=SUPPORTED_RUNTIME_EXECUTION_MODES, default=defaults.runtime_execution_mode)
    parser.add_argument("--runtime-probe-frequency", type=int, default=defaults.runtime_probe_frequency)
    parser.add_argument("--runtime-probe-policy", choices=SUPPORTED_SIDECAR_POLICIES, default=defaults.runtime_probe_policy)
    parser.add_argument("--runtime-calibration-snapshot", type=str, default=defaults.runtime_calibration_snapshot)
    parser.add_argument("--runtime-auto-batch-shot-threshold", type=int, default=defaults.runtime_auto_batch_shot_threshold)
    parser.add_argument("--runtime-retry-attempts", type=int, default=defaults.runtime_retry_attempts)
    parser.add_argument("--runtime-retry-backoff-seconds", type=float, default=defaults.runtime_retry_backoff_seconds)
    parser.add_argument("--runtime-checkpoint-every", type=int, default=defaults.runtime_checkpoint_every)
    parser.add_argument("--runtime-estimated-total-shots", type=int, default=defaults.runtime_estimated_total_shots)
    parser.add_argument("--runtime-run-label", type=str, default=defaults.runtime_run_label)
    parser.add_argument("--shot-governor-enabled", dest="shot_governor_enabled", action="store_true")
    parser.add_argument("--no-shot-governor", dest="shot_governor_enabled", action="store_false")
    parser.set_defaults(shot_governor_enabled=True)
    parser.add_argument("--shot-governor-budget-multiplier", type=float, default=defaults.shot_governor_budget_multiplier)
    parser.add_argument("--shot-governor-patience", type=int, default=defaults.shot_governor_patience)
    parser.add_argument("--shot-governor-min-improvement", type=float, default=defaults.shot_governor_min_improvement)
    parser.add_argument("--shot-governor-escalation", type=float, default=defaults.shot_governor_escalation)
    parser.add_argument("--shot-governor-min-shots", type=int, default=defaults.shot_governor_min_shots)
    parser.add_argument("--shot-governor-max-shots", type=int, default=defaults.shot_governor_max_shots)
    parser.add_argument("--shot-governor-max-cumulative-shots", type=int, default=defaults.shot_governor_max_cumulative_shots)
    parser.add_argument("--runtime-checkpoint-enabled", dest="runtime_checkpoint_enabled", action="store_true")
    parser.add_argument("--no-runtime-checkpoint", dest="runtime_checkpoint_enabled", action="store_false")
    parser.set_defaults(runtime_checkpoint_enabled=True)
    parser.add_argument("--runtime-resume-enabled", dest="runtime_resume_enabled", action="store_true")
    parser.add_argument("--no-runtime-resume", dest="runtime_resume_enabled", action="store_false")
    parser.set_defaults(runtime_resume_enabled=True)
    parser.add_argument("--tracker-backend", choices=SUPPORTED_TRACKERS, default=defaults.tracker_backend)
    parser.add_argument("--tracker-uri", type=str, default=defaults.tracker_uri)
    parser.add_argument("--bo-epoch-strategy", choices=SUPPORTED_BO_EPOCH_STRATEGIES, default=defaults.bo_epoch_strategy)
    parser.add_argument("--noise-level", type=float, default=defaults.noise_level)
    parser.add_argument("--penalty-epoch-length", type=int, default=defaults.penalty_epoch_length)
    parser.add_argument("--study-num-seeds", type=int, default=defaults.study_num_seeds)
    parser.add_argument("--study-n-spins", dest="study_n_spins", type=str, default=",".join(str(v) for v in defaults.study_n_spins))
    parser.add_argument("--study-budget-ratio", type=float, default=defaults.study_budget_ratio)
    parser.add_argument("--study-depths", type=str, default=",".join(str(v) for v in defaults.study_depths))
    parser.add_argument("--study-shot-budgets", type=str, default=",".join(str(v) for v in defaults.study_shot_budgets))
    parser.add_argument("--study-noise-levels", type=str, default=",".join(str(v) for v in defaults.study_noise_levels))
    parser.add_argument("--study-j2-ratios", type=str, default=",".join(str(v) for v in defaults.study_j2_ratios))
    parser.add_argument("--study-disorder-levels", type=str, default=",".join(str(v) for v in defaults.study_disorder_levels))
    parser.add_argument("--output-prefix", type=str, default=defaults.output_prefix)
    parser.add_argument("--execution-body-input", type=str, default=None)
    parser.add_argument("--trust-policy", type=str, default=None)
    parser.add_argument("--runtime-trust-output", type=str, default=None)

    parser.add_argument("--use-noise", dest="use_noise", action="store_true")
    parser.add_argument("--no-noise", dest="use_noise", action="store_false")
    parser.set_defaults(use_noise=True)

    parser.add_argument("--use-zne", dest="use_zne", action="store_true")
    parser.add_argument("--no-zne", dest="use_zne", action="store_false")
    parser.set_defaults(use_zne=True)

    parser.add_argument("--use-readout-mitigation", dest="use_readout_mitigation", action="store_true")
    parser.add_argument("--no-readout-mitigation", dest="use_readout_mitigation", action="store_false")
    parser.set_defaults(use_readout_mitigation=True)

    parser.add_argument("--dynamic-shots", dest="dynamic_shots_enabled", action="store_true")
    parser.add_argument("--fixed-shots", dest="dynamic_shots_enabled", action="store_false")
    parser.set_defaults(dynamic_shots_enabled=True)

    parser.add_argument("--use-twirling", dest="use_twirling", action="store_true")
    parser.add_argument("--no-twirling", dest="use_twirling", action="store_false")
    parser.set_defaults(use_twirling=False)

    parser.add_argument("--use-dynamical-decoupling", dest="use_dynamical_decoupling", action="store_true")
    parser.add_argument("--no-dynamical-decoupling", dest="use_dynamical_decoupling", action="store_false")
    parser.set_defaults(use_dynamical_decoupling=False)
    return parser


def _parse_int_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def _parse_float_tuple(value: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def deck_from_args(args: argparse.Namespace) -> RunDeck:
    magnetization_m = int(args.magnetization_m)
    if args.budget is not None:
        magnetization_m = int(2 * args.budget - args.n_spins)
    cfg = RunDeck(
        seed=args.seed,
        n_spins=args.n_spins,
        magnetization_m=magnetization_m,
        j1_coupling=args.j1_coupling,
        j2_coupling=args.j2_coupling,
        disorder_strength=args.disorder_strength,
        h_field=args.h_field,
        bond_dilution_prob=args.bond_dilution_prob,
        lattice_type=args.lattice_type,
        depth=args.depth,
        fourier_modes=args.fourier_modes,
        base_shots=args.base_shots,
        cvar_alpha=args.cvar_alpha,
        bo_iters=args.bo_iters,
        sobol_init_iters=args.sobol_init_iters,
        spsa_iters=args.spsa_iters,
        random_search_iters=args.random_search_iters,
        classical_bo_iters=args.classical_bo_iters,
        parameterization=args.parameterization,
        constraint_handling=args.constraint_handling,
        runtime_mode=args.runtime_mode,
        runtime_backend=args.runtime_backend,
        runtime_execution_mode=args.runtime_execution_mode,
        runtime_auto_batch_shot_threshold=args.runtime_auto_batch_shot_threshold,
        runtime_retry_attempts=args.runtime_retry_attempts,
        runtime_retry_backoff_seconds=args.runtime_retry_backoff_seconds,
        runtime_checkpoint_every=args.runtime_checkpoint_every,
        runtime_estimated_total_shots=args.runtime_estimated_total_shots,
        runtime_run_label=args.runtime_run_label,
        runtime_checkpoint_enabled=args.runtime_checkpoint_enabled,
        runtime_resume_enabled=args.runtime_resume_enabled,
        shot_governor_enabled=args.shot_governor_enabled,
        shot_governor_budget_multiplier=args.shot_governor_budget_multiplier,
        shot_governor_patience=args.shot_governor_patience,
        shot_governor_min_improvement=args.shot_governor_min_improvement,
        shot_governor_escalation=args.shot_governor_escalation,
        shot_governor_min_shots=args.shot_governor_min_shots,
        shot_governor_max_shots=args.shot_governor_max_shots,
        shot_governor_max_cumulative_shots=args.shot_governor_max_cumulative_shots,
        tracker_backend=args.tracker_backend,
        tracker_uri=args.tracker_uri,
        bo_epoch_strategy=args.bo_epoch_strategy,
        runtime_probe_frequency=args.runtime_probe_frequency,
        runtime_probe_policy=args.runtime_probe_policy,
        runtime_calibration_snapshot=args.runtime_calibration_snapshot,
        noise_level=args.noise_level,
        penalty_epoch_length=args.penalty_epoch_length,
        study_num_seeds=args.study_num_seeds,
        study_n_spins=_parse_int_tuple(args.study_n_spins),
        study_budget_ratio=args.study_budget_ratio,
        study_depths=_parse_int_tuple(args.study_depths),
        study_shot_budgets=_parse_int_tuple(args.study_shot_budgets),
        study_noise_levels=_parse_float_tuple(args.study_noise_levels),
        study_j2_ratios=_parse_float_tuple(args.study_j2_ratios),
        study_disorder_levels=_parse_float_tuple(args.study_disorder_levels),
        use_noise=args.use_noise,
        use_zne=args.use_zne,
        use_readout_mitigation=args.use_readout_mitigation,
        dynamic_shots_enabled=args.dynamic_shots_enabled,
        use_twirling=args.use_twirling,
        use_dynamical_decoupling=args.use_dynamical_decoupling,
        output_prefix=args.output_prefix,
    )
    cfg.validate()
    return cfg


def _stdout_progress(payload: dict[str, object]) -> None:
    print(json_dumps_clean(payload), flush=True)


def _stdout_result(event: str, payload: dict[str, object]) -> None:
    print(json_dumps_clean({"event": event, **payload}), flush=True)


def _load_runtime_trust_gate(path: str | None) -> RuntimeTrustGate:
    if path is None:
        return RuntimeTrustGate(
            max_calibration_age_seconds=1800.0,
            max_two_qubit_gate_inflation=2.0,
            max_confidence_interval_width=0.2,
            max_mitigation_shift=0.1,
            max_observable_error=0.2,
        )
    text = Path(path).read_text()
    if path.endswith(".json"):
        payload = json.loads(text)
    else:
        payload = _parse_flat_policy(text)
    return RuntimeTrustGate(**payload)


def _parse_flat_policy(text: str) -> dict[str, object]:
    payload: dict[str, object] = {}
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or ":" not in stripped:
            continue
        key, value = (part.strip() for part in stripped.split(":", 1))
        if value.lower() in {"true", "false"}:
            payload[key] = value.lower() == "true"
        else:
            payload[key] = float(value)
    return payload


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    normalized_mode = {"advisor": "decision"}.get(args.mode, args.mode)
    if normalized_mode not in {"smoke", "single", "study", "decision", "live_cert", "runtime_trust_report"}:
        parser.error(f"Unsupported mode: {args.mode}")
    if normalized_mode == "runtime_trust_report":
        if not args.execution_body_input:
            parser.error("--execution-body-input is required for runtime_trust_report.")
        gate = _load_runtime_trust_gate(args.trust_policy)
        records = load_execution_deformation_csv(args.execution_body_input)
        report = build_runtime_trust_report(records, gate)
        if args.runtime_trust_output:
            Path(args.runtime_trust_output).write_text(report)
        else:
            print(report, flush=True)
        return
    cfg = deck_from_args(args)
    if normalized_mode == "smoke":
        result = run_smoke_test(cfg)
    elif normalized_mode == "single":
        result = run_single_benchmark(cfg)
    elif normalized_mode == "decision":
        result = run_decision(cfg)
    elif normalized_mode == "live_cert":
        cert = run_live_certification_check(cfg, backend_name=cfg.runtime_backend)
        save_certification_report(cert, f"{cfg.output_prefix}_live_cert_report")
        result = cert.as_dict()
    else:
        result = run_benchmark_study(cfg, progress_callback=_stdout_progress)
        _stdout_result("study_result", sanitize_json_payload(result))
        return
    print(json_dumps_clean(result, indent=2), flush=True)


if __name__ == "__main__":
    main()


__all__ = [
    "build_parser",
    "deck_from_args",
    "main",
]
