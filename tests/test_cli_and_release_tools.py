from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from spinmesh_runtime.cli import build_parser, deck_from_args
from spinmesh_runtime.config import SUPPORTED_TRACKERS
from spinmesh_runtime.logging_utils import setup_logging


def test_cli_exposes_resume_and_tracker_controls() -> None:
    parser = build_parser()
    args = parser.parse_args([
        '--runtime-estimated-total-shots', '1234',
        '--runtime-run-label', 'resume-a',
        '--no-runtime-checkpoint',
        '--no-runtime-resume',
        '--tracker-backend', 'none',
        '--tracker-uri', 'sqlite:///tmp.db',
    ])
    cfg = deck_from_args(args)
    assert cfg.runtime_estimated_total_shots == 1234
    assert cfg.runtime_run_label == 'resume-a'
    assert cfg.runtime_checkpoint_enabled is False
    assert cfg.runtime_resume_enabled is False
    assert cfg.tracker_backend in SUPPORTED_TRACKERS
    assert cfg.tracker_uri == 'sqlite:///tmp.db'


def test_cleanup_release_dry_run_lists_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / '__pycache__'
    cache_dir.mkdir()
    target = cache_dir / 'junk.pyc'
    target.write_bytes(b'abc')
    proc = subprocess.run([sys.executable, 'tools/cleanup_release.py', '--root', str(tmp_path), '--dry-run'], capture_output=True, text=True, check=True)
    assert '__pycache__' in proc.stdout or 'junk.pyc' in proc.stdout


def test_frustration_axis_sweep_dry_run_emits_grid(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            'tools/run_frustration_axis_sweep.py',
            '--output-dir',
            str(tmp_path),
            '--dry-run',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"n_spins": 8' in proc.stdout
    assert '"shots": 256' in proc.stdout
    assert '"bo_fourier"' in proc.stdout


def test_frustration_axis_aer_sweep_dry_run_emits_execution_body(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            'tools/run_frustration_axis_aer_sweep.py',
            '--output-dir',
            str(tmp_path),
            '--dry-run',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"topology_model": "forked_heavy_hex"' in proc.stdout
    assert '"shots": 2048' in proc.stdout


def test_live_validation_dry_run_emits_report_plan(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            'tools/run_live_validation.py',
            '--output-prefix',
            str(tmp_path / 'live_suite'),
            '--runtime-mode',
            'runtime_v2',
            '--runtime-backend',
            'ibm_fez',
            '--live-repeats',
            '2',
            '--aer-repeats',
            '2',
            '--dry-run',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"mode": "dry_run"' in proc.stdout
    assert '"runtime_backend": "ibm_fez"' in proc.stdout
    assert 'live_suite.json' in proc.stdout
    assert 'live_suite_backend_snapshot.json' in proc.stdout


def test_runtime_trust_report_cli_reads_execution_body_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "execution_deformation_records.csv"
    csv_path.write_text(
        "problem_id,backend_name,calibration_snapshot_id,calibration_age_seconds,n_spins,p_layers,j1,j2,h,"
        "source_circuit_depth,transpiled_circuit_depth,two_qubit_gate_count,swap_count,layout_distance_score,"
        "shots,queue_delay_seconds,session_duration_seconds,energy_error_vs_exact,energy_error_vs_ideal_qaoa,"
        "magnetization_error,correlation_error,structure_factor_error,phase_label_changed,sample_variance,"
        "confidence_interval_width,mitigation_shift,mitigation_instability,runtime_seconds,quantum_decision,rejection_reason\n"
        "p1,aer,snap,60,6,2,1.0,0.5,0.0,20,24,18,0,1.0,1024,0,1,0.01,0.02,0.01,0.01,,false,0.02,0.05,0.01,0.01,1.0,run_quantum,\n"
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "spinmesh_runtime.cli",
            "--mode",
            "runtime_trust_report",
            "--execution-body-input",
            str(csv_path),
            "--trust-policy",
            "configs/runtime_trust_gate.yaml",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
        check=True,
    )
    assert "# Runtime Decision Boundary" in proc.stdout
    assert "accept_quantum_result" in proc.stdout


def test_setup_logging_writes_under_logs_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    logger = setup_logging("runtime_aware_qaoa")
    try:
        logger.info("hello log")
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
    root_logs = list(tmp_path.glob("runtime_aware_qaoa_*.log"))
    nested_logs = list((tmp_path / "logs").glob("runtime_aware_qaoa_*.log"))
    assert root_logs == []
    assert len(nested_logs) == 1
