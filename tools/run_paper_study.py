from __future__ import annotations

import argparse
from dataclasses import asdict
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from spinmesh_runtime.config import RunDeck
from spinmesh_runtime.pipeline import run_benchmark_study
from spinmesh_runtime.tracking import json_dumps_clean


def _parse_int_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def _parse_float_tuple(value: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def _artifact_plan(prefix: Path) -> dict[str, str]:
    return {
        "results_json_glob": f"{prefix}_*_results.json",
        "summary_csv_glob": f"{prefix}_*_summary.csv",
        "sqlite_glob": f"{prefix}_*.sqlite",
        "aggregates_path": str(Path(f"{prefix}_aggregates.csv")),
        "performance_profile_path": str(Path(f"{prefix}_performance_profile.csv")),
        "findings_json_path": str(Path(f"{prefix}_findings.json")),
        "findings_md_path": str(Path(f"{prefix}_findings.md")),
        "findings_tex_path": str(Path(f"{prefix}_findings.tex")),
        "utility_frontier_path": str(Path(f"{prefix}_utility_frontier.csv")),
        "decision_json_path": str(Path(f"{prefix}_decision_report.json")),
        "decision_md_path": str(Path(f"{prefix}_decision_report.md")),
        "executive_summary_path": str(Path(f"{prefix}_executive_summary.md")),
        "progress_path": str(Path(f"{prefix}_progress.json")),
        "approx_gap_plot": str(prefix.with_name(prefix.name + "_approx_gap.png")),
        "sample_efficiency_plot": str(prefix.with_name(prefix.name + "_sample_efficiency.png")),
        "success_vs_noise_plot": str(prefix.with_name(prefix.name + "_success_vs_noise.png")),
        "valid_ratio_vs_depth_plot": str(prefix.with_name(prefix.name + "_valid_ratio_vs_depth.png")),
        "valid_sector_ratio_vs_spins_plot": str(prefix.with_name(prefix.name + "_valid_sector_ratio_vs_spins.png")),
        "energy_gap_vs_j2_ratio_plot": str(prefix.with_name(prefix.name + "_energy_gap_vs_j2_ratio.png")),
        "mitigation_vs_shots_plot": str(prefix.with_name(prefix.name + "_mitigation_vs_shots.png")),
        "performance_profile_plot": str(prefix.with_name(prefix.name + "_performance_profile.png")),
    }


def _profile_defaults(profile: str) -> dict[str, object]:
    if profile == "full":
        return {
            "study_num_seeds": 3,
            "study_n_spins": "4,6,8",
            "study_depths": "1,2,3",
            "study_shot_budgets": "64,128,256",
            "study_noise_levels": "0.0,0.04,0.08",
            "study_j2_ratios": "0.0,0.25,0.5,0.75,1.0",
            "study_disorder_levels": "0.0,0.1,0.3",
            "study_budget_ratio": 0.5,
            "base_shots": 64,
            "bo_iters": 8,
            "sobol_init_iters": 4,
            "spsa_iters": 8,
            "random_search_iters": 8,
            "classical_bo_iters": 8,
        }
    return {
        "study_num_seeds": 2,
        "study_n_spins": "4,6,8",
        "study_depths": "1,2",
        "study_shot_budgets": "64,128",
        "study_noise_levels": "0.0,0.04,0.08",
        "study_j2_ratios": "0.25,0.5,0.75",
        "study_disorder_levels": "0.0,0.3",
        "study_budget_ratio": 0.5,
        "base_shots": 64,
        "bo_iters": 6,
        "sobol_init_iters": 3,
        "spsa_iters": 6,
        "random_search_iters": 6,
        "classical_bo_iters": 6,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a larger J1-J2 Ising submission-oriented benchmark study.")
    parser.add_argument("--profile", choices=("draft", "full"), default="draft")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "results" / "paper_draft"))
    parser.add_argument("--label", default="submission_draft")
    parser.add_argument("--runtime-mode", choices=("local_proxy", "aer"), default="local_proxy")
    parser.add_argument("--study-num-seeds", type=int)
    parser.add_argument("--study-n-spins", type=str)
    parser.add_argument("--study-depths", type=str)
    parser.add_argument("--study-shot-budgets", type=str)
    parser.add_argument("--study-noise-levels", type=str)
    parser.add_argument("--study-j2-ratios", type=str)
    parser.add_argument("--study-disorder-levels", type=str)
    parser.add_argument("--study-budget-ratio", type=float)
    parser.add_argument("--base-shots", type=int)
    parser.add_argument("--bo-iters", type=int)
    parser.add_argument("--sobol-init-iters", type=int)
    parser.add_argument("--spsa-iters", type=int)
    parser.add_argument("--random-search-iters", type=int)
    parser.add_argument("--classical-bo-iters", type=int)
    parser.add_argument("--dry-run", action="store_true", help="Print the resolved configuration and expected artifact paths without running the study.")
    return parser


def _resolved_value(args: argparse.Namespace, field_name: str, defaults: dict[str, object]) -> object:
    value = getattr(args, field_name)
    return defaults[field_name] if value is None else value


def _build_cfg(args: argparse.Namespace, prefix: Path) -> RunDeck:
    defaults = _profile_defaults(args.profile)
    n_spins = _parse_int_tuple(str(_resolved_value(args, "study_n_spins", defaults)))
    depths = _parse_int_tuple(str(_resolved_value(args, "study_depths", defaults)))
    shot_budgets = _parse_int_tuple(str(_resolved_value(args, "study_shot_budgets", defaults)))
    noise_levels = _parse_float_tuple(str(_resolved_value(args, "study_noise_levels", defaults)))
    j2_ratios = _parse_float_tuple(str(_resolved_value(args, "study_j2_ratios", defaults)))
    disorder_levels = _parse_float_tuple(str(_resolved_value(args, "study_disorder_levels", defaults)))
    budget_ratio = float(_resolved_value(args, "study_budget_ratio", defaults))
    base_shots = int(_resolved_value(args, "base_shots", defaults))
    initial_budget = max(1, int(round(n_spins[0] * budget_ratio)))
    cfg = RunDeck(
        runtime_mode=args.runtime_mode,
        lattice_type="j1j2_frustrated",
        n_spins=n_spins[0],
        magnetization_m=2 * initial_budget - n_spins[0],
        depth=depths[0],
        fourier_modes=1,
        base_shots=base_shots,
        bo_iters=int(_resolved_value(args, "bo_iters", defaults)),
        sobol_init_iters=int(_resolved_value(args, "sobol_init_iters", defaults)),
        spsa_iters=int(_resolved_value(args, "spsa_iters", defaults)),
        random_search_iters=int(_resolved_value(args, "random_search_iters", defaults)),
        classical_bo_iters=int(_resolved_value(args, "classical_bo_iters", defaults)),
        use_noise=any(level > 0.0 for level in noise_levels),
        use_zne=True,
        use_readout_mitigation=True,
        study_num_seeds=int(_resolved_value(args, "study_num_seeds", defaults)),
        study_n_spins=n_spins,
        study_budget_ratio=budget_ratio,
        study_depths=depths,
        study_shot_budgets=shot_budgets,
        study_noise_levels=noise_levels,
        study_j2_ratios=j2_ratios,
        study_disorder_levels=disorder_levels,
        tracker_backend="sqlite",
        output_prefix=str(prefix),
    )
    cfg.validate()
    return cfg


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(output_dir / ".mpl-cache"))
    prefix = output_dir / args.label
    cfg = _build_cfg(args, prefix)
    planned_artifacts = _artifact_plan(prefix)

    if args.dry_run:
        payload = {
            "mode": "dry_run",
            "profile": args.profile,
            "runtime_mode": args.runtime_mode,
            "output_prefix": str(prefix),
            "config": asdict(cfg),
            "planned_artifacts": planned_artifacts,
        }
        print(json_dumps_clean(payload, indent=2))
        return

    result = run_benchmark_study(cfg)
    manifest = {
        "profile": args.profile,
        "label": args.label,
        "runtime_mode": args.runtime_mode,
        "output_prefix": str(prefix),
        "config": asdict(cfg),
        "artifacts": {key: value for key, value in result.items() if key.endswith("_path")},
        "planned_artifacts": planned_artifacts,
        "summary": {
            "n_records": result["summary"]["n_records"],
            "n_trials": result["summary"]["n_trials"],
            "recommendation": result["summary"]["decision_report"]["recommendation"],
        },
    }
    manifest_path = output_dir / f"{args.label}_manifest.json"
    manifest_path.write_text(json_dumps_clean(manifest, indent=2))
    print(json_dumps_clean({"manifest_path": str(manifest_path), **manifest}, indent=2))


if __name__ == "__main__":
    main()
