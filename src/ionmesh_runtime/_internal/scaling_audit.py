from __future__ import annotations

from datetime import datetime
from math import comb
from pathlib import Path
from statistics import mean
from typing import Any

from .config import RunDeck
from .pipeline import run_smoke_test
from .tracking import json_dumps_clean, sanitize_json_payload


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _budget_for_system_size(n_spins: int, budget_ratio: float) -> int:
    return max(1, min(n_spins, int(round(n_spins * budget_ratio))))


def _scaling_cfg(
    *,
    runtime_mode: str,
    n_spins: int,
    budget_ratio: float,
    base_shots: int,
    depth: int,
    seed: int,
) -> RunDeck:
    return RunDeck(
        runtime_mode=runtime_mode,
        n_spins=n_spins,
        magnetization_m=2 * _budget_for_system_size(n_spins, budget_ratio) - n_spins,
        depth=depth,
        fourier_modes=1,
        base_shots=base_shots,
        bo_iters=1,
        sobol_init_iters=1,
        spsa_iters=1,
        random_search_iters=1,
        classical_bo_iters=1,
        use_noise=False,
        use_zne=False,
        use_readout_mitigation=False,
        dynamic_shots_enabled=False,
        shot_governor_enabled=False,
        runtime_probe_readout_each_eval=False,
        runtime_probe_policy="never",
        seed=seed,
    )


def _growth_factors(rows: list[dict[str, Any]]) -> list[dict[str, float | int]]:
    factors: list[dict[str, float | int]] = []
    for left, right in zip(rows, rows[1:]):
        left_runtime = float(left.get("runtime_seconds", 0.0))
        right_runtime = float(right.get("runtime_seconds", 0.0))
        factors.append(
            {
                "from_n_spins": int(left["n_spins"]),
                "to_n_spins": int(right["n_spins"]),
                "runtime_growth_factor": float(right_runtime / left_runtime) if left_runtime > 0.0 else float("inf"),
                "state_space_growth_factor": float(right["state_space_size"] / left["state_space_size"]),
            }
        )
    return factors


def _assessment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row.get("status") == "completed"]
    failed = [row for row in rows if row.get("status") != "completed"]
    if not completed:
        return {
            "max_completed_n_spins": None,
            "applicable_for_tested_scale": False,
            "reason": "no scaling cells completed",
        }
    runtimes = [float(row["runtime_seconds"]) for row in completed]
    valid_ratios = [float(row["valid_ratio"]) for row in completed]
    return {
        "max_completed_n_spins": int(completed[-1]["n_spins"]),
        "applicable_for_tested_scale": bool(completed[-1]["status"] == "completed"),
        "mean_runtime_seconds": float(mean(runtimes)),
        "max_runtime_seconds": float(max(runtimes)),
        "mean_valid_ratio": float(mean(valid_ratios)),
        "min_valid_ratio": float(min(valid_ratios)),
        "failure_count": len(failed),
        "failed_cells": [int(row["n_spins"]) for row in failed],
        "takeaway": (
            "The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_spins."
            if not failed
            else "The current implementation did not complete every tested cell, which bounds the practical scaling envelope on this machine."
        ),
    }


def run_scaling_audit(
    *,
    runtime_mode: str,
    n_spins_values: tuple[int, ...],
    budget_ratio: float = 0.5,
    base_shots: int = 32,
    depth: int = 1,
    seed: int = 42,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for n_spins in n_spins_values:
        cfg = _scaling_cfg(
            runtime_mode=runtime_mode,
            n_spins=n_spins,
            budget_ratio=budget_ratio,
            base_shots=base_shots,
            depth=depth,
            seed=seed,
        )
        row: dict[str, Any] = {
            "n_spins": int(n_spins),
            "budget": int(cfg.budget),
            "depth": int(cfg.depth),
            "base_shots": int(cfg.base_shots),
            "state_space_size": int(2**n_spins),
            "feasible_space_size": int(comb(n_spins, cfg.budget)),
        }
        try:
            result = sanitize_json_payload(run_smoke_test(cfg))
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)
            rows.append(row)
            continue
        row.update(
            {
                "status": "completed",
                "runtime_seconds": float(result.get("runtime_seconds", 0.0)),
                "valid_ratio": float(result.get("valid_ratio", 0.0)),
                "measurement_success_probability": float(result.get("measurement_success_probability", 0.0)),
                "best_energy": float(result.get("best_energy", 0.0)),
                "exact_energy": float(result.get("exact_energy", 0.0)),
                "total_shots": int(result.get("total_shots", 0)),
                "final_readout_shots": int(result.get("final_readout_shots", 0)),
                "objective_calls": int(result.get("objective_calls", 0)),
                "sampler_calls": int(result.get("sampler_calls", 0)),
                "transpilation_metadata": result.get("transpilation_metadata", {}),
            }
        )
        rows.append(row)

    return {
        "observed_at": _now_iso(),
        "runtime_mode": runtime_mode,
        "budget_ratio": float(budget_ratio),
        "base_shots": int(base_shots),
        "depth": int(depth),
        "seed": int(seed),
        "rows": rows,
        "growth_factors": _growth_factors([row for row in rows if row.get("status") == "completed"]),
        "assessment": _assessment(rows),
    }


def save_scaling_audit_report(result: dict[str, Any], output_prefix: str | Path) -> tuple[Path, Path]:
    base = Path(output_prefix)
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json_dumps_clean(result, indent=2))

    assessment = result.get("assessment", {})
    lines = [
        "# Scaling Audit Report",
        "",
        f"- observed_at: `{result.get('observed_at')}`",
        f"- runtime_mode: `{result.get('runtime_mode')}`",
        f"- tested n_spins values: `{[row.get('n_spins') for row in result.get('rows', [])]}`",
        f"- max completed n_spins: `{assessment.get('max_completed_n_spins')}`",
        f"- mean runtime seconds: `{assessment.get('mean_runtime_seconds')}`",
        f"- max runtime seconds: `{assessment.get('max_runtime_seconds')}`",
        f"- mean valid ratio: `{assessment.get('mean_valid_ratio')}`",
        f"- min valid ratio: `{assessment.get('min_valid_ratio')}`",
        "",
        "## Assessment",
        "",
        f"- applicable_for_tested_scale: `{assessment.get('applicable_for_tested_scale')}`",
        f"- takeaway: {assessment.get('takeaway')}",
        "",
        "## Rows",
        "",
    ]
    for row in result.get("rows", []):
        if row.get("status") == "completed":
            lines.append(
                f"- n={row['n_spins']} | state_space={row['state_space_size']} | runtime={row['runtime_seconds']:.4f}s | "
                f"valid_ratio={row['valid_ratio']:.4f} | P_succ={row['measurement_success_probability']:.4f}"
            )
        else:
            lines.append(f"- n={row['n_spins']} | failed | error={row.get('error')}")
    md_path.write_text("\n".join(lines).rstrip() + "\n")
    return json_path, md_path


__all__ = [
    'run_scaling_audit',
    'save_scaling_audit_report',
]
