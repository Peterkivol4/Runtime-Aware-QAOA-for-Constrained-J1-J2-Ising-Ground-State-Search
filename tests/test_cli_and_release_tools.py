from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hybrid_qaoa_portfolio.cli import build_parser, deck_from_args
from hybrid_qaoa_portfolio.config import SUPPORTED_TRACKERS
from hybrid_qaoa_portfolio.logging_utils import setup_logging


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


def test_pilot_study_dry_run_emits_manifest_plan(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            'tools/run_pilot_study.py',
            '--output-dir',
            str(tmp_path),
            '--label',
            'pilot_case',
            '--runtime-mode',
            'aer',
            '--dry-run',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"mode": "dry_run"' in proc.stdout
    assert '"runtime_mode": "aer"' in proc.stdout
    assert 'pilot_case_manifest.json' not in proc.stdout
    assert 'pilot_case_aggregates.csv' in proc.stdout


def test_paper_study_dry_run_emits_profile_and_artifact_plan(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            'tools/run_paper_study.py',
            '--output-dir',
            str(tmp_path),
            '--label',
            'paper_case',
            '--profile',
            'draft',
            '--runtime-mode',
            'aer',
            '--dry-run',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"mode": "dry_run"' in proc.stdout
    assert '"profile": "draft"' in proc.stdout
    assert '"runtime_mode": "aer"' in proc.stdout
    assert 'paper_case_performance_profile.csv' in proc.stdout


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


def test_scaling_audit_dry_run_emits_report_plan(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            'tools/run_scaling_audit.py',
            '--runtime-mode',
            'local_proxy',
            '--n-spins',
            '4,6,8',
            '--output-prefix',
            str(tmp_path / 'scaling_audit'),
            '--dry-run',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"mode": "dry_run"' in proc.stdout
    assert '"runtime_mode": "local_proxy"' in proc.stdout
    assert 'scaling_audit.json' in proc.stdout


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
