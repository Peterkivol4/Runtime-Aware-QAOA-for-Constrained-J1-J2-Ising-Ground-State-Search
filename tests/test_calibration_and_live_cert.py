from __future__ import annotations

from pathlib import Path

from spinmesh_runtime.calibration_snapshot import compare_snapshot_files
from spinmesh_runtime.config import RunDeck
from spinmesh_runtime.live_certification import save_certification_report, CertificationResult


def test_compare_snapshot_files(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text('{"backend_name": "a", "basis_gates": ["rz", "sx"], "qubits": [{"t1": 1.0, "t2": 2.0, "readout_error": 0.01}], "instruction_errors": {"cx": [0.02]}}')
    right.write_text('{"backend_name": "b", "basis_gates": ["rz", "sx", "cx"], "qubits": [{"t1": 1.5, "t2": 2.5, "readout_error": 0.02}], "instruction_errors": {"cx": [0.03]}}')
    report = compare_snapshot_files(left, right)
    assert report["backend_sensitivity_score"] >= 0.0
    assert report["stability_class"] in {"stable", "drifting"}


def test_save_live_certification_report(tmp_path: Path) -> None:
    result = CertificationResult(passed=False, checks={"runtime_available": False}, notes=["offline"]) 
    json_path, md_path = save_certification_report(result, tmp_path / "cert_report")
    assert json_path.exists()
    assert md_path.exists()
    assert "offline" in md_path.read_text()
