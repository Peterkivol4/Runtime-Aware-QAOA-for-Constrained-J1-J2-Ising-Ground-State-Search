from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PATTERNS = [
    '.pytest_cache',
    '__pycache__',
    '_tmp_run*',
    'tmp_*',
    '.mypy_cache',
    '.ruff_cache',
    '.coverage',
    'htmlcov',
    'logs',
    'dist',
    'build',
    '*.egg-info',
    'mlruns',
    '*.pyc',
    '*.pyo',
    '*.log',
    '*.qpy',
    '*_results.json',
    '*_summary.csv',
    '*_aggregates.csv',
    '*_findings.json',
    '*_findings.md',
    '*_findings.tex',
    '*_performance_profile.csv',
    '*_utility_frontier.csv',
    '*_decision_report.json',
    '*_decision_report.md',
    '*_executive_summary.md',
    '*_live_cert_report.json',
    '*_live_cert_report.md',
    'single_*.json',
    'smoke*.json',
    'release_*.json',
    'release_*.csv',
    'release_*.md',
    'release_*.tex',
    '*_approx_gap.png',
    '*_sample_efficiency.png',
    '*_success_vs_noise.png',
    '*_valid_ratio_vs_depth.png',
    '*_valid_sector_ratio_vs_spins.png',
    '*_mitigation_vs_shots.png',
    '*_performance_profile.png',
    '*.sqlite',
    '*.sqlite-*',
]


def remove_path(path: Path, *, dry_run: bool = False) -> None:
    if dry_run:
        print(path)
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink(missing_ok=True)


def main(root: str = '.', *, dry_run: bool = False) -> None:
    base = Path(root)
    for pattern in PATTERNS:
        for path in base.rglob(pattern):
            remove_path(path, dry_run=dry_run)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Remove generated artifacts before packaging a release.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    main(args.root, dry_run=args.dry_run)
