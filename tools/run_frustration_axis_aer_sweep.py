from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "spinmesh_mplconfig"))

from ionmesh_runtime._internal.problem import IsingSpinProblem
from ionmesh_runtime._internal.tracking import json_dumps_clean
from ionmesh_runtime._internal.optional_deps import load_matplotlib_pyplot
from tools.run_execution_body_experiments import (
    _angles,
    _base_cfg,
    _build_parametric_qaoa_circuit,
    _execute_body,
    _optimize_frozen_angles,
)


def _parse_float_tuple(value: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else math.nan


def _std(values: list[float]) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def _ci95(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(1.96 * _std(values) / math.sqrt(len(values)))


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ratios = _parse_float_tuple(args.j2_ratios)
    base_cfg = _base_cfg().copy_with(
        n_spins=6,
        magnetization_m=0,
        depth=args.depth,
        base_shots=args.shots,
        disorder_strength=args.disorder_strength,
        h_field=args.h_field,
        use_readout_mitigation=False,
        use_zne=False,
    )
    layouts = {"scattered": [0, 2, 4, 1, 3, 5]}
    rows: list[dict[str, Any]] = []
    started = time.time()
    for ratio in ratios:
        for seed in range(args.seed, args.seed + args.num_seeds):
            cfg = base_cfg.copy_with(seed=seed, j2_coupling=float(ratio) * base_cfg.j1_coupling)
            problem = IsingSpinProblem(cfg)
            params, source_metrics = _optimize_frozen_angles(cfg, problem)
            gamma, beta = _angles(params, cfg.depth)
            source_measured = _build_parametric_qaoa_circuit(cfg, gamma, beta, measure=True)
            row, _, _, _ = _execute_body(
                cfg=cfg,
                problem=problem,
                params=params,
                source_metrics=source_metrics,
                source_depth=int(source_measured.depth()),
                topology_model=args.topology_model,
                optimization_level=args.transpiler_optimization_level,
                initial_layout_policy="scattered",
                initial_layout=layouts["scattered"],
                routing_method=args.routing_method,
                shots=args.shots,
                noise_scale=args.noise_scale,
                calibration_age_seconds=args.calibration_age_seconds,
                session_policy="single_session",
                mitigation_policy="none",
                seed_offset=seed,
            )
            row["experiment"] = "frustration_axis_aer"
            row["j2_ratio"] = float(ratio)
            row["seed"] = int(seed)
            row["frustration_index"] = problem.frustration_index
            row["energy_gap_to_second_lowest"] = problem.energy_gap_to_second_lowest
            row["exact_feasible_energy"] = problem.exact_feasible_energy
            rows.append(row)

    aggregate_rows = _aggregate(rows)
    records_path = output_dir / "frustration_axis_aer_records.csv"
    aggregates_path = output_dir / "frustration_axis_aer_aggregates.csv"
    plot_path = output_dir / "valid_ratio_vs_j2_ratio_aer.png"
    report_path = output_dir / "valid_ratio_frustration_axis_aer_report.md"
    summary_path = output_dir / "frustration_axis_aer_summary.json"
    _write_csv(records_path, rows)
    _write_csv(aggregates_path, aggregate_rows)
    _plot(aggregate_rows, plot_path)
    center = _center_vs_edges(aggregate_rows)
    report_path.write_text(
        _render_report(
            args=args,
            aggregate_rows=aggregate_rows,
            ratios=ratios,
            records_path=records_path,
            aggregates_path=aggregates_path,
            plot_path=plot_path,
            elapsed_seconds=time.time() - started,
            center=center,
        )
    )
    summary = {
        "records": len(rows),
        "ratios": list(ratios),
        "seeds": list(range(args.seed, args.seed + args.num_seeds)),
        "n_spins": base_cfg.n_spins,
        "depth": args.depth,
        "shots": args.shots,
        "topology_model": args.topology_model,
        "routing_method": args.routing_method,
        "transpiler_optimization_level": args.transpiler_optimization_level,
        "records_path": str(records_path),
        "aggregates_path": str(aggregates_path),
        "plot_path": str(plot_path),
        "report_path": str(report_path),
        "elapsed_seconds": time.time() - started,
        "center_vs_edges": center,
    }
    summary_path.write_text(json_dumps_clean(summary, indent=2))
    return summary


def _aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregate_rows: list[dict[str, Any]] = []
    for ratio in sorted({float(row["j2_ratio"]) for row in rows}):
        chunk = [row for row in rows if float(row["j2_ratio"]) == ratio]
        valid = [float(row["valid_ratio"]) for row in chunk]
        corr = [float(row["correlation_error"]) for row in chunk]
        mag = [float(row["magnetization_error"]) for row in chunk]
        aggregate_rows.append(
            {
                "j2_ratio": ratio,
                "n": len(chunk),
                "mean_valid_ratio": _mean(valid),
                "std_valid_ratio": _std(valid),
                "ci95_valid_ratio": _ci95(valid),
                "collapse_fraction": float(np.mean([value < 0.5 for value in valid])) if valid else math.nan,
                "mean_correlation_error": _mean(corr),
                "mean_magnetization_error": _mean(mag),
                "mean_frustration_index": _mean([float(row["frustration_index"]) for row in chunk]),
                "mean_routing_inflation": _mean([float(row["routing_inflation"]) for row in chunk]),
                "mean_two_qubit_gate_count": _mean([float(row["two_qubit_gate_count"]) for row in chunk]),
            }
        )
    return aggregate_rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _plot(aggregate_rows: list[dict[str, Any]], output_path: Path) -> None:
    plt = load_matplotlib_pyplot()
    chunk = sorted(aggregate_rows, key=lambda row: float(row["j2_ratio"]))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(
        [float(row["j2_ratio"]) for row in chunk],
        [float(row["mean_valid_ratio"]) for row in chunk],
        yerr=[float(row["ci95_valid_ratio"]) for row in chunk],
        marker="o",
        capsize=3,
        linewidth=1.8,
    )
    ax.axhline(0.5, color="firebrick", linestyle="--", alpha=0.75, label="collapse threshold")
    ax.axvline(0.5, color="gray", linestyle=":", alpha=0.85, label="J2/J1 = 0.5")
    ax.set_title("Aer routed valid-sector collapse across J2/J1")
    ax.set_xlabel("J2/J1 ratio")
    ax.set_ylabel("Mean valid-sector ratio")
    ax.set_ylim(0.0, 1.0)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _center_vs_edges(aggregate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ratio = {round(float(row["j2_ratio"]), 10): row for row in aggregate_rows}
    center = float(by_ratio[0.5]["mean_valid_ratio"])
    edge_mean = _mean([float(by_ratio[ratio]["mean_valid_ratio"]) for ratio in (0.0, 1.0)])
    shoulder_mean = _mean([float(by_ratio[ratio]["mean_valid_ratio"]) for ratio in (0.4, 0.6)])
    return {
        "center_mean_valid_ratio": center,
        "edge_mean_valid_ratio": edge_mean,
        "shoulder_mean_valid_ratio": shoulder_mean,
        "center_minus_edge_mean": center - edge_mean,
        "center_minus_shoulder_mean": center - shoulder_mean,
        "center_is_lower_than_edges": bool(center < edge_mean),
        "center_is_lower_than_shoulders": bool(center < shoulder_mean),
    }


def _render_report(
    *,
    args: argparse.Namespace,
    aggregate_rows: list[dict[str, Any]],
    ratios: tuple[float, ...],
    records_path: Path,
    aggregates_path: Path,
    plot_path: Path,
    elapsed_seconds: float,
    center: dict[str, Any],
) -> str:
    interpretation = (
        "The hardware-like routed Aer sweep reproduces valid-sector collapse, but the collapse is broad rather than sharply localized at `J2/J1 = 0.5`."
    )
    if center["center_is_lower_than_edges"] and center["center_is_lower_than_shoulders"]:
        interpretation = "The hardware-like routed Aer sweep reproduces collapse and shows a local dip at `J2/J1 = 0.5`."
    lines = [
        "# Aer Routed Valid-Ratio Collapse Across the Frustration Axis",
        "",
        "## Fixed sweep design",
        "",
        "- backend model: `AerSimulator` with generic routed backend",
        f"- topology model: `{args.topology_model}`",
        f"- transpiler optimization level: `{args.transpiler_optimization_level}`",
        f"- routing method: `{args.routing_method}`",
        "- `n_spins`: `6`",
        f"- QAOA depth: `p = {args.depth}`",
        f"- shots per ratio/seed: `{args.shots}`",
        f"- seeds: `{args.seed}` through `{args.seed + args.num_seeds - 1}`",
        f"- `J2/J1` ratios: `{', '.join(f'{ratio:.1f}' for ratio in ratios)}`",
        f"- elapsed wall-clock seconds: `{elapsed_seconds:.2f}`",
        "",
        "The source-level angles are selected by the same deterministic statevector search procedure for each ratio/seed, then the measured circuit is transpiled and sampled under the same execution body.",
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
        "## Aggregate table",
        "",
        _markdown_table(
            aggregate_rows,
            [
                "j2_ratio",
                "n",
                "mean_valid_ratio",
                "ci95_valid_ratio",
                "collapse_fraction",
                "mean_correlation_error",
                "mean_routing_inflation",
                "mean_two_qubit_gate_count",
            ],
        ),
        "",
        "## Artifacts",
        "",
        f"- records CSV: `{records_path}`",
        f"- aggregates CSV: `{aggregates_path}`",
        f"- plot: `{plot_path}`",
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
    parser = argparse.ArgumentParser(description="Run a routed Aer valid-ratio sweep across J2/J1.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "results" / "frustration_axis_aer"))
    parser.add_argument("--j2-ratios", default="0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0")
    parser.add_argument("--seed", type=int, default=910)
    parser.add_argument("--num-seeds", type=int, default=3)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--shots", type=int, default=2048)
    parser.add_argument("--noise-scale", type=float, default=1.0)
    parser.add_argument("--disorder-strength", type=float, default=0.0)
    parser.add_argument("--h-field", type=float, default=0.0)
    parser.add_argument("--calibration-age-seconds", type=float, default=120.0)
    parser.add_argument("--topology-model", choices=("forked_heavy_hex", "line", "star"), default="forked_heavy_hex")
    parser.add_argument("--routing-method", default="sabre")
    parser.add_argument("--transpiler-optimization-level", type=int, choices=(0, 1, 2, 3), default=1)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "output_dir": args.output_dir,
                    "ratios": list(_parse_float_tuple(args.j2_ratios)),
                    "seeds": list(range(args.seed, args.seed + args.num_seeds)),
                    "depth": args.depth,
                    "shots": args.shots,
                    "topology_model": args.topology_model,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    print(json_dumps_clean(run(args), indent=2))


if __name__ == "__main__":
    main()
