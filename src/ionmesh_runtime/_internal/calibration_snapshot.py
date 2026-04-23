from __future__ import annotations

from pathlib import Path

from .tracking import json_dumps_clean
from typing import Any

import numpy as np

from .runtime_support import RuntimeSamplerFactory, runtime_status


def export_backend_snapshot(backend_name: str, output_path: str | Path) -> Path:
    status = runtime_status()
    if not status.available:  # pragma: no cover - optional dependency
        raise ImportError(status.message)
    service = RuntimeSamplerFactory.create_service(strict=True)
    return RuntimeSamplerFactory.save_calibration_snapshot(service, backend_name, output_path)


def load_snapshot(snapshot_path: str | Path) -> dict[str, Any]:
    return RuntimeSamplerFactory.load_calibration_snapshot(snapshot_path)


def compare_snapshots(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    def _avg(snapshot: dict[str, Any], key: str) -> float | None:
        values = [q.get(key) for q in snapshot.get("qubits", []) if q.get(key) is not None]
        return float(np.mean(values)) if values else None

    left_err = RuntimeSamplerFactory.noise_profile_from_snapshot(left)
    right_err = RuntimeSamplerFactory.noise_profile_from_snapshot(right)
    basis_overlap = len(set(left.get("basis_gates", [])) & set(right.get("basis_gates", []))) / max(
        1, len(set(left.get("basis_gates", [])) | set(right.get("basis_gates", [])))
    )
    report = {
        "left_backend": left.get("backend_name"),
        "right_backend": right.get("backend_name"),
        "basis_overlap": float(basis_overlap),
        "readout_error_drift": None if left_err["readout_p10"] is None or right_err["readout_p10"] is None else float(right_err["readout_p10"] - left_err["readout_p10"]),
        "depol_error_drift": float(right_err["depol_error"] - left_err["depol_error"]),
        "t1_drift": None if _avg(left, "t1") is None or _avg(right, "t1") is None else float(_avg(right, "t1") - _avg(left, "t1")),
        "t2_drift": None if _avg(left, "t2") is None or _avg(right, "t2") is None else float(_avg(right, "t2") - _avg(left, "t2")),
    }
    magnitude = abs(report["depol_error_drift"]) + abs(report["readout_error_drift"] or 0.0)
    report["stability_class"] = "stable" if magnitude < 0.01 else "drifting"
    report["backend_sensitivity_score"] = float(magnitude + (1.0 - basis_overlap))
    return report


def compare_snapshot_files(left_path: str | Path, right_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    report = compare_snapshots(load_snapshot(left_path), load_snapshot(right_path))
    if output_path is not None:
        Path(output_path).write_text(json_dumps_clean(report, indent=2))
    return report

__all__ = [
    'export_backend_snapshot',
    'load_snapshot',
    'compare_snapshots',
    'compare_snapshot_files',
]
