from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from .config import RunDeck
from .live_certification import run_live_certification_check
from .pipeline import run_smoke_test
from .runtime_support import RuntimeSamplerFactory, runtime_status
from .tracking import json_dumps_clean, sanitize_json_payload


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _budget_for_system_size(cfg: RunDeck, n_spins: int) -> int:
    if cfg.study_budget_ratio is not None:
        return max(1, min(n_spins, int(round(n_spins * cfg.study_budget_ratio))))
    if n_spins == cfg.n_assets:
        return cfg.budget
    scaled = cfg.budget / max(1, cfg.n_assets)
    return max(1, min(n_spins, int(round(n_spins * scaled))))


def _smoke_validation_cfg(cfg: RunDeck, **updates: Any) -> RunDeck:
    payload = {
        "depth": 1,
        "fourier_modes": 1,
        "bo_iters": 1,
        "sobol_init_iters": 1,
        "random_search_iters": 1,
        "spsa_iters": 1,
        "use_zne": False,
        "use_readout_mitigation": False,
        "dynamic_shots_enabled": False,
        "shot_governor_enabled": False,
        "runtime_probe_readout_each_eval": False,
        "runtime_probe_policy": "never",
    }
    payload.update(updates)
    return cfg.copy_with(**payload)


def _run_smoke_bundle(cfg: RunDeck, *, label: str) -> dict[str, Any]:
    started_at = _now_iso()
    result = sanitize_json_payload(run_smoke_test(cfg))
    return {
        "label": label,
        "observed_at": started_at,
        "config": {
            "seed": cfg.seed,
            "runtime_mode": cfg.runtime_mode,
            "runtime_backend": cfg.runtime_backend,
            "runtime_execution_mode": cfg.runtime_execution_mode,
            "n_spins": cfg.n_spins,
            "budget": cfg.budget,
            "depth": cfg.depth,
            "base_shots": cfg.base_shots,
            "noise_level": cfg.noise_level,
        },
        "result": result,
    }


def _summary_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "stdev": None, "min": None, "max": None}
    return {
        "mean": float(mean(values)),
        "stdev": float(pstdev(values)) if len(values) > 1 else 0.0,
        "min": float(min(values)),
        "max": float(max(values)),
    }


def _summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    best_energies = [float(run["result"]["best_energy"]) for run in runs]
    valid_ratios = [float(run["result"]["valid_ratio"]) for run in runs]
    runtimes = [float(run["result"].get("runtime_seconds", 0.0)) for run in runs]
    success_prob = [float(run["result"].get("measurement_success_probability", 0.0)) for run in runs]
    return {
        "count": len(runs),
        "best_energy": _summary_stats(best_energies),
        "valid_ratio": _summary_stats(valid_ratios),
        "runtime_seconds": _summary_stats(runtimes),
        "measurement_success_probability": _summary_stats(success_prob),
        "valid_ratio_below_half_fraction": float(sum(value < 0.5 for value in valid_ratios) / len(valid_ratios)) if valid_ratios else None,
    }


def _parity_summary(hardware_runs: list[dict[str, Any]], aer_runs: list[dict[str, Any]]) -> dict[str, Any]:
    pair_count = min(len(hardware_runs), len(aer_runs))
    if pair_count <= 0:
        return {"pair_count": 0}
    energy_deltas = []
    valid_ratio_deltas = []
    runtime_deltas = []
    for index in range(pair_count):
        hardware = hardware_runs[index]["result"]
        aer = aer_runs[index]["result"]
        energy_deltas.append(float(hardware["best_energy"]) - float(aer["best_energy"]))
        valid_ratio_deltas.append(float(hardware["valid_ratio"]) - float(aer["valid_ratio"]))
        runtime_deltas.append(float(hardware.get("runtime_seconds", 0.0)) - float(aer.get("runtime_seconds", 0.0)))
    return {
        "pair_count": pair_count,
        "delta_best_energy_hardware_minus_aer": _summary_stats(energy_deltas),
        "delta_valid_ratio_hardware_minus_aer": _summary_stats(valid_ratio_deltas),
        "delta_runtime_seconds_hardware_minus_aer": _summary_stats(runtime_deltas),
    }


def _appendix_pairs(
    cfg: RunDeck,
    *,
    aer_noise_profile: dict[str, float] | None,
    appendix_n_spins: tuple[int, ...],
    appendix_shot_budgets: tuple[int, ...],
    appendix_seeds: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n_spins in appendix_n_spins:
        budget = _budget_for_system_size(cfg, n_spins)
        for base_shots in appendix_shot_budgets:
            for seed_offset in range(appendix_seeds):
                seed = cfg.seed + seed_offset
                base_cfg = _smoke_validation_cfg(
                    cfg,
                    seed=seed,
                    n_spins=n_spins,
                    magnetization_m=2 * budget - n_spins,
                    base_shots=base_shots,
                )
                hardware_cfg = base_cfg.copy_with(runtime_mode="runtime_v2")
                aer_updates = {"runtime_mode": "aer"}
                if aer_noise_profile:
                    aer_updates.update(aer_noise_profile)
                aer_cfg = base_cfg.copy_with(**aer_updates)
                cell_label = f"n{n_spins}_shots{base_shots}_seed{seed}"
                rows.append(
                    {
                        "label": cell_label,
                        "config": {
                            "seed": seed,
                            "n_spins": n_spins,
                            "budget": budget,
                            "base_shots": base_shots,
                            "depth": 1,
                        },
                        "hardware": _run_smoke_bundle(hardware_cfg, label=f"{cell_label}_hardware"),
                        "aer": _run_smoke_bundle(aer_cfg, label=f"{cell_label}_aer"),
                    }
                )
    return rows


def _appendix_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"cell_count": 0}
    energy_deltas = []
    valid_ratio_deltas = []
    for row in rows:
        hardware = row["hardware"]["result"]
        aer = row["aer"]["result"]
        energy_deltas.append(float(hardware["best_energy"]) - float(aer["best_energy"]))
        valid_ratio_deltas.append(float(hardware["valid_ratio"]) - float(aer["valid_ratio"]))
    return {
        "cell_count": len(rows),
        "delta_best_energy_hardware_minus_aer": _summary_stats(energy_deltas),
        "delta_valid_ratio_hardware_minus_aer": _summary_stats(valid_ratio_deltas),
        "hardware_valid_ratio_below_half_fraction": float(
            sum(float(row["hardware"]["result"]["valid_ratio"]) < 0.5 for row in rows) / len(rows)
        ),
        "aer_valid_ratio_below_half_fraction": float(
            sum(float(row["aer"]["result"]["valid_ratio"]) < 0.5 for row in rows) / len(rows)
        ),
    }


def run_live_validation_suite(
    cfg: RunDeck,
    *,
    live_repeats: int = 2,
    aer_repeats: int = 2,
    appendix_n_spins: tuple[int, ...] = (4, 6),
    appendix_shot_budgets: tuple[int, ...] = (32, 64),
    appendix_seeds: int = 1,
) -> dict[str, Any]:
    if live_repeats <= 0:
        raise ValueError("live_repeats must be positive.")
    if aer_repeats <= 0:
        raise ValueError("aer_repeats must be positive.")
    if appendix_seeds <= 0:
        raise ValueError("appendix_seeds must be positive.")

    result: dict[str, Any] = {
        "observed_at": _now_iso(),
        "runtime_status": asdict(runtime_status()),
    }

    live_cfg = _smoke_validation_cfg(cfg, runtime_mode="runtime_v2")
    cert = run_live_certification_check(live_cfg, backend_name=live_cfg.runtime_backend)
    result["preflight"] = cert.as_dict()

    calibration_snapshot: dict[str, Any] | None = None
    aer_noise_profile: dict[str, float] | None = None
    if cert.passed:
        service = RuntimeSamplerFactory.create_service(live_cfg, strict=True)
        backend = RuntimeSamplerFactory.select_backend(service, live_cfg.runtime_backend)
        calibration_snapshot = RuntimeSamplerFactory.calibration_snapshot_payload(backend)
        aer_noise_profile = RuntimeSamplerFactory.noise_profile_from_snapshot(calibration_snapshot)
    result["calibration_snapshot"] = calibration_snapshot
    result["aer_noise_profile"] = aer_noise_profile

    live_repeat_runs = [
        _run_smoke_bundle(live_cfg.copy_with(seed=live_cfg.seed + index), label=f"hardware_repeat_{index + 1}")
        for index in range(live_repeats)
    ]
    aer_cfg = _smoke_validation_cfg(cfg, runtime_mode="aer", **(aer_noise_profile or {}))
    aer_repeat_runs = [
        _run_smoke_bundle(aer_cfg.copy_with(seed=aer_cfg.seed + index), label=f"aer_repeat_{index + 1}")
        for index in range(aer_repeats)
    ]

    appendix_pairs = _appendix_pairs(
        cfg,
        aer_noise_profile=aer_noise_profile,
        appendix_n_spins=appendix_n_spins,
        appendix_shot_budgets=appendix_shot_budgets,
        appendix_seeds=appendix_seeds,
    )

    result["repeatability"] = {
        "hardware_runs": live_repeat_runs,
        "hardware_summary": _summarize_runs(live_repeat_runs),
        "aer_runs": aer_repeat_runs,
        "aer_summary": _summarize_runs(aer_repeat_runs),
        "parity_summary": _parity_summary(live_repeat_runs, aer_repeat_runs),
    }
    result["appendix_sweep"] = {
        "pairs": appendix_pairs,
        "summary": _appendix_summary(appendix_pairs),
    }
    return sanitize_json_payload(result)


def save_live_validation_report(result: dict[str, Any], output_prefix: str | Path) -> tuple[Path, Path, Path | None]:
    base = Path(output_prefix)
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    snapshot_path: Path | None = None
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json_dumps_clean(result, indent=2))

    snapshot = result.get("calibration_snapshot")
    if isinstance(snapshot, dict) and snapshot:
        snapshot_path = base.with_name(f"{base.name}_backend_snapshot").with_suffix(".json")
        snapshot_path.write_text(json_dumps_clean(snapshot, indent=2))

    preflight = result.get("preflight", {})
    repeatability = result.get("repeatability", {})
    appendix = result.get("appendix_sweep", {})
    hardware_summary = repeatability.get("hardware_summary", {})
    parity_summary = repeatability.get("parity_summary", {})
    appendix_summary = appendix.get("summary", {})

    lines = [
        "# Live Validation Report",
        "",
        f"- observed_at: `{result.get('observed_at')}`",
        f"- preflight passed: **{preflight.get('passed')}**",
        f"- backend: `{preflight.get('checks', {}).get('backend_name')}`",
        f"- requested execution mode: `{preflight.get('checks', {}).get('selected_execution_mode')}`",
        "",
        "## Repeatability",
        "",
        f"- hardware repeats: `{hardware_summary.get('count')}`",
        f"- hardware mean best energy: `{hardware_summary.get('best_energy', {}).get('mean')}`",
        f"- hardware best-energy stdev: `{hardware_summary.get('best_energy', {}).get('stdev')}`",
        f"- hardware mean valid ratio: `{hardware_summary.get('valid_ratio', {}).get('mean')}`",
        "",
        "## Aer Parity",
        "",
        f"- paired comparisons: `{parity_summary.get('pair_count')}`",
        f"- mean best-energy delta (hardware - Aer): `{parity_summary.get('delta_best_energy_hardware_minus_aer', {}).get('mean')}`",
        f"- mean valid-ratio delta (hardware - Aer): `{parity_summary.get('delta_valid_ratio_hardware_minus_aer', {}).get('mean')}`",
        "",
        "## Appendix Sweep",
        "",
        f"- paired cells: `{appendix_summary.get('cell_count')}`",
        f"- hardware valid-ratio < 0.5 fraction: `{appendix_summary.get('hardware_valid_ratio_below_half_fraction')}`",
        f"- Aer valid-ratio < 0.5 fraction: `{appendix_summary.get('aer_valid_ratio_below_half_fraction')}`",
    ]
    if snapshot_path is not None:
        lines.extend(["", "## Snapshot", "", f"- backend snapshot: `{snapshot_path.name}`"])
    md_path.write_text("\n".join(lines).rstrip() + "\n")
    return json_path, md_path, snapshot_path


__all__ = [
    'run_live_validation_suite',
    'save_live_validation_report',
]
