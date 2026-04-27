from __future__ import annotations

import argparse
import csv
import json
import math
import os
import tempfile
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "spinmesh_mplconfig"))

from ionmesh_runtime._internal.config import RunDeck
from ionmesh_runtime._internal.optional_deps import load_matplotlib_pyplot
from ionmesh_runtime._internal.pipeline import _evaluate_qaoa
from ionmesh_runtime._internal.problem import IsingSpinProblem
from ionmesh_runtime._internal.tracking import json_dumps_clean


DEFAULT_METHODS = ("bo_fourier", "spsa_fourier", "random_fourier", "bo_direct")


def _parse_float_tuple(value: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def _parse_str_tuple(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else math.nan


def _std(values: list[float]) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def _ci95(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(1.96 * _std(values) / math.sqrt(len(values)))


def _base_cfg(args: argparse.Namespace) -> RunDeck:
    cfg = RunDeck(
        runtime_mode="local_proxy",
        seed=args.seed,
        lattice_type="j1j2_frustrated",
        n_spins=args.n_spins,
        magnetization_m=args.magnetization_m,
        j1_coupling=1.0,
        j2_coupling=0.5,
        disorder_strength=args.disorder_strength,
        h_field=args.h_field,
        depth=args.depth,
        fourier_modes=args.fourier_modes,
        base_shots=args.shots,
        cvar_alpha=args.cvar_alpha,
        bo_iters=args.iters,
        sobol_init_iters=min(args.sobol_init_iters, args.iters),
        spsa_iters=args.iters,
        random_search_iters=args.iters,
        use_noise=args.noise_level > 0.0,
        noise_level=args.noise_level,
        use_readout_mitigation=False,
        use_zne=False,
        dynamic_shots_enabled=False,
        shot_governor_enabled=False,
        runtime_checkpoint_enabled=False,
        runtime_resume_enabled=False,
        tracker_backend="none",
        constraint_handling=args.constraint_handling,
    )
    cfg.validate()
    return cfg


def _problem_summary(problem: IsingSpinProblem) -> dict[str, Any]:
    return {
        "exact_feasible_energy": problem.exact_feasible_energy,
        "exact_feasible_bitstring": problem.exact_feasible_bitstring,
        "frustration_index": problem.frustration_index,
        "energy_gap_to_second_lowest": problem.energy_gap_to_second_lowest,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ratios = _parse_float_tuple(args.j2_ratios)
    methods = _parse_str_tuple(args.methods)
    base_cfg = _base_cfg(args)
    rows: list[dict[str, Any]] = []
    started = time.time()

    for j2_ratio in ratios:
        for seed in range(args.seed, args.seed + args.num_seeds):
            cfg = base_cfg.copy_with(
                seed=seed,
                j2_coupling=float(j2_ratio) * base_cfg.j1_coupling,
                runtime_run_label=f"frustration_axis_j2_{j2_ratio:.1f}_seed_{seed}",
            )
            problem = IsingSpinProblem(cfg)
            problem_payload = _problem_summary(problem)
            for method in methods:
                outcome = _evaluate_qaoa(cfg, problem, method).record
                row = outcome.as_dict()
                row.pop("trace", None)
                row.update(problem_payload)
                row["j2_ratio"] = float(j2_ratio)
                row["seed"] = int(seed)
                row["method"] = method
                row["fixed_n_spins"] = cfg.n_spins
                row["fixed_depth"] = cfg.depth
                row["fixed_shots"] = cfg.base_shots
                row["fixed_noise_level"] = cfg.noise_level
                row["fixed_disorder_strength"] = cfg.disorder_strength
                rows.append(row)

    aggregate_rows = _aggregate(rows)
    records_path = output_dir / "frustration_axis_valid_ratio_records.csv"
    aggregates_path = output_dir / "frustration_axis_valid_ratio_aggregates.csv"
    _write_csv(records_path, rows)
    _write_csv(aggregates_path, aggregate_rows)
    plot_path = output_dir / "valid_ratio_vs_j2_ratio.png"
    _plot_valid_ratio(aggregate_rows, plot_path)
    report_path = output_dir / "valid_ratio_frustration_axis_report.md"
    report = _render_report(
        rows=rows,
        aggregate_rows=aggregate_rows,
        ratios=ratios,
        methods=methods,
        args=args,
        records_path=records_path,
        aggregates_path=aggregates_path,
        plot_path=plot_path,
        elapsed_seconds=time.time() - started,
    )
    report_path.write_text(report)
    summary = {
        "records": len(rows),
        "aggregates": len(aggregate_rows),
        "ratios": list(ratios),
        "methods": list(methods),
        "n_spins": args.n_spins,
        "depth": args.depth,
        "shots": args.shots,
        "num_seeds": args.num_seeds,
        "output_dir": str(output_dir),
        "records_path": str(records_path),
        "aggregates_path": str(aggregates_path),
        "plot_path": str(plot_path),
        "report_path": str(report_path),
        "elapsed_seconds": time.time() - started,
        "center_vs_edges": _center_vs_edges(aggregate_rows),
    }
    summary_path = output_dir / "frustration_axis_valid_ratio_summary.json"
    summary_path.write_text(json_dumps_clean(summary, indent=2))
    return summary


def _aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregate_rows: list[dict[str, Any]] = []
    groups = sorted({(str(row["method"]), float(row["j2_ratio"])) for row in rows}, key=lambda item: (item[0], item[1]))
    for method, ratio in groups:
        chunk = [row for row in rows if str(row["method"]) == method and float(row["j2_ratio"]) == ratio]
        valid = [float(row["valid_ratio"]) for row in chunk]
        gap = [float(row["approximation_gap"]) for row in chunk]
        p_succ = [float(row["measurement_success_probability"]) for row in chunk]
        frustration = [float(row["frustration_index"]) for row in chunk if row.get("frustration_index") not in {None, ""}]
        aggregate_rows.append(
            {
                "method": method,
                "j2_ratio": ratio,
                "n": len(chunk),
                "mean_valid_ratio": _mean(valid),
                "std_valid_ratio": _std(valid),
                "ci95_valid_ratio": _ci95(valid),
                "collapse_fraction": float(np.mean([value < 0.5 for value in valid])) if valid else math.nan,
                "mean_approximation_gap": _mean(gap),
                "mean_success_probability": _mean(p_succ),
                "mean_frustration_index": _mean(frustration),
            }
        )

    all_groups = sorted({float(row["j2_ratio"]) for row in rows})
    for ratio in all_groups:
        chunk = [row for row in rows if float(row["j2_ratio"]) == ratio]
        valid = [float(row["valid_ratio"]) for row in chunk]
        gap = [float(row["approximation_gap"]) for row in chunk]
        aggregate_rows.append(
            {
                "method": "all_qaoa_methods",
                "j2_ratio": ratio,
                "n": len(chunk),
                "mean_valid_ratio": _mean(valid),
                "std_valid_ratio": _std(valid),
                "ci95_valid_ratio": _ci95(valid),
                "collapse_fraction": float(np.mean([value < 0.5 for value in valid])) if valid else math.nan,
                "mean_approximation_gap": _mean(gap),
                "mean_success_probability": _mean([float(row["measurement_success_probability"]) for row in chunk]),
                "mean_frustration_index": _mean([float(row["frustration_index"]) for row in chunk if row.get("frustration_index") not in {None, ""}]),
            }
        )
    return aggregate_rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames = sorted({key for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _plot_valid_ratio(aggregate_rows: list[dict[str, Any]], output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    fig, ax = plt.subplots(figsize=(8, 5))
    methods = [method for method in sorted({str(row["method"]) for row in aggregate_rows}) if method != "all_qaoa_methods"]
    for method in methods:
        chunk = sorted([row for row in aggregate_rows if row["method"] == method], key=lambda row: float(row["j2_ratio"]))
        x = [float(row["j2_ratio"]) for row in chunk]
        y = [float(row["mean_valid_ratio"]) for row in chunk]
        err = [float(row["ci95_valid_ratio"]) for row in chunk]
        ax.errorbar(x, y, yerr=err, marker="o", linewidth=1.2, capsize=3, alpha=0.75, label=method)
    all_chunk = sorted([row for row in aggregate_rows if row["method"] == "all_qaoa_methods"], key=lambda row: float(row["j2_ratio"]))
    ax.plot(
        [float(row["j2_ratio"]) for row in all_chunk],
        [float(row["mean_valid_ratio"]) for row in all_chunk],
        color="black",
        marker="s",
        linewidth=2.4,
        label="all QAOA methods mean",
    )
    ax.axhline(0.5, color="firebrick", linestyle="--", linewidth=1.2, alpha=0.75, label="collapse threshold")
    ax.axvline(0.5, color="gray", linestyle=":", linewidth=1.4, alpha=0.85, label="J2/J1 = 0.5")
    ax.set_title("Valid-sector ratio across the J2/J1 frustration axis")
    ax.set_xlabel("J2/J1 ratio")
    ax.set_ylabel("Mean valid-sector ratio")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _center_vs_edges(aggregate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    all_rows = [row for row in aggregate_rows if row["method"] == "all_qaoa_methods"]
    by_ratio = {round(float(row["j2_ratio"]), 10): row for row in all_rows}
    center = by_ratio.get(0.5)
    edges = [by_ratio[ratio] for ratio in (0.0, 1.0) if ratio in by_ratio]
    shoulders = [by_ratio[ratio] for ratio in (0.4, 0.6) if ratio in by_ratio]
    center_value = float(center["mean_valid_ratio"]) if center else math.nan
    edge_mean = _mean([float(row["mean_valid_ratio"]) for row in edges])
    shoulder_mean = _mean([float(row["mean_valid_ratio"]) for row in shoulders])
    return {
        "center_mean_valid_ratio": center_value,
        "edge_mean_valid_ratio": edge_mean,
        "shoulder_mean_valid_ratio": shoulder_mean,
        "center_minus_edge_mean": center_value - edge_mean if math.isfinite(edge_mean) else math.nan,
        "center_minus_shoulder_mean": center_value - shoulder_mean if math.isfinite(shoulder_mean) else math.nan,
        "center_is_lower_than_edges": bool(center_value < edge_mean) if math.isfinite(edge_mean) else False,
        "center_is_lower_than_shoulders": bool(center_value < shoulder_mean) if math.isfinite(shoulder_mean) else False,
    }


def _render_report(
    *,
    rows: list[dict[str, Any]],
    aggregate_rows: list[dict[str, Any]],
    ratios: tuple[float, ...],
    methods: tuple[str, ...],
    args: argparse.Namespace,
    records_path: Path,
    aggregates_path: Path,
    plot_path: Path,
    elapsed_seconds: float,
) -> str:
    all_rows = sorted([row for row in aggregate_rows if row["method"] == "all_qaoa_methods"], key=lambda row: float(row["j2_ratio"]))
    center = _center_vs_edges(aggregate_rows)
    if center["center_is_lower_than_edges"] and center["center_is_lower_than_shoulders"]:
        interpretation = "The fine sweep shows a local valid-ratio dip at the nominal maximally frustrated point."
    elif center["center_is_lower_than_edges"]:
        interpretation = "The fine sweep shows lower valid ratio at `J2/J1 = 0.5` than at the endpoints, but not a clean local dip relative to the adjacent shoulders."
    else:
        interpretation = "The fine sweep does not show a sharper valid-ratio collapse exactly at `J2/J1 = 0.5`; collapse is broad across the frustrated axis under this fixed proxy setting."
    lines = [
        "# Valid-Ratio Collapse Across the Frustration Axis",
        "",
        "## Fixed sweep design",
        "",
        f"- `n_spins`: `{args.n_spins}`",
        f"- `magnetization_m`: `{args.magnetization_m}`",
        f"- QAOA depth: `p = {args.depth}`",
        f"- final readout shots per method/seed/ratio: `{args.shots}`",
        f"- optimizer iterations per method: `{args.iters}`",
        f"- seeds: `{args.seed}` through `{args.seed + args.num_seeds - 1}`",
        f"- `J2/J1` ratios: `{', '.join(f'{ratio:.1f}' for ratio in ratios)}`",
        f"- methods: `{', '.join(methods)}`",
        f"- noise level: `{args.noise_level}`",
        f"- disorder strength: `{args.disorder_strength}`",
        f"- elapsed wall-clock seconds: `{elapsed_seconds:.2f}`",
        "",
        "The shot governor is disabled for this sweep, so the final-readout shot budget is fixed across the whole frustration axis.",
        "",
        "## Main interpretation",
        "",
        interpretation,
        "",
        f"- center mean valid ratio: `{center['center_mean_valid_ratio']:.6g}`",
        f"- endpoint mean valid ratio: `{center['edge_mean_valid_ratio']:.6g}`",
        f"- adjacent-shoulder mean valid ratio (`0.4`, `0.6`): `{center['shoulder_mean_valid_ratio']:.6g}`",
        f"- center minus endpoints: `{center['center_minus_edge_mean']:.6g}`",
        f"- center minus shoulders: `{center['center_minus_shoulder_mean']:.6g}`",
        "",
        "## All-method valid-ratio aggregate",
        "",
        _markdown_table(
            all_rows,
            ["j2_ratio", "n", "mean_valid_ratio", "ci95_valid_ratio", "collapse_fraction", "mean_approximation_gap", "mean_frustration_index"],
        ),
        "",
        "## Method-level aggregate",
        "",
        _markdown_table(
            [row for row in aggregate_rows if row["method"] != "all_qaoa_methods"],
            ["method", "j2_ratio", "n", "mean_valid_ratio", "ci95_valid_ratio", "collapse_fraction", "mean_approximation_gap"],
        ),
        "",
        "## Artifacts",
        "",
        f"- records CSV: `{_display_path(records_path)}`",
        f"- aggregates CSV: `{_display_path(aggregates_path)}`",
        f"- plot: `{_display_path(plot_path)}`",
        "",
        "## Scientific caution",
        "",
        "This is a controlled local-proxy sweep, not a hardware claim. It isolates the frustration-axis dependence under fixed depth and shot budget; hardware routing and calibration-body deformation remain covered by `results/execution_body/`.",
    ]
    return "\n".join(lines) + "\n"


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a fixed-depth valid-ratio sweep across J2/J1.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "results" / "frustration_axis"))
    parser.add_argument("--j2-ratios", default="0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0")
    parser.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    parser.add_argument("--seed", type=int, default=810)
    parser.add_argument("--num-seeds", type=int, default=5)
    parser.add_argument("--n-spins", type=int, default=8)
    parser.add_argument("--magnetization-m", type=int, default=0)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--fourier-modes", type=int, default=2)
    parser.add_argument("--shots", type=int, default=256)
    parser.add_argument("--iters", type=int, default=6)
    parser.add_argument("--sobol-init-iters", type=int, default=3)
    parser.add_argument("--cvar-alpha", type=float, default=0.25)
    parser.add_argument("--noise-level", type=float, default=0.04)
    parser.add_argument("--disorder-strength", type=float, default=0.3)
    parser.add_argument("--h-field", type=float, default=0.0)
    parser.add_argument("--constraint-handling", choices=("remap", "penalty"), default="remap")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.dry_run:
        payload = {
            "output_dir": args.output_dir,
            "ratios": list(_parse_float_tuple(args.j2_ratios)),
            "methods": list(_parse_str_tuple(args.methods)),
            "n_spins": args.n_spins,
            "depth": args.depth,
            "shots": args.shots,
            "num_seeds": args.num_seeds,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(json_dumps_clean(run(args), indent=2))


if __name__ == "__main__":
    main()
