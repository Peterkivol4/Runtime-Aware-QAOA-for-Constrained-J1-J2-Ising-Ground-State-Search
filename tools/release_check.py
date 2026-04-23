from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

JUNK_PATTERNS = [
    '__pycache__',
    '.pytest_cache',
    '_tmp_run*',
    'tmp_*',
    '*.pyc',
    '*.pyo',
    '*.log',
    '*.sqlite',
    '*.sqlite-*',
    '*_results.json',
    '*_summary.csv',
    'single_*.json',
    'smoke*.json',
    'release_*.json',
    'release_*.csv',
    'release_*.md',
    'release_*.tex',
]

REQUIRED_DOCS = [
    'docs/ARCHITECTURE.md',
    'docs/HONEST_LIMITATIONS.md',
    'docs/LIVE_CERT_PROTOCOL.md',
]


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
    print('>>>', ' '.join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def assert_clean(repo: Path) -> None:
    for pattern in JUNK_PATTERNS:
        matches = [p for p in repo.rglob(pattern) if '.venv' not in p.parts]
        if matches:
            raise RuntimeError(f'Found release junk for pattern {pattern}: {matches[:5]}')


def assert_release_docs(repo: Path) -> None:
    missing = [doc for doc in REQUIRED_DOCS if not (repo / doc).exists()]
    if missing:
        raise RuntimeError(f'Missing required release docs: {missing}')
    for path in repo.rglob('*.md'):
        if '.venv' in path.parts:
            continue
        content = path.read_text(encoding='utf-8', errors='ignore').strip()
        if path.name.endswith('_decision_report.md') and len(content.splitlines()) < 8:
            raise RuntimeError(f'Decision-report markdown artifact looks too thin: {path}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Run release-grade validation for the repository.')
    parser.add_argument('--repo', default='.')
    parser.add_argument('--skip-aer', action='store_true')
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    env = dict(os.environ)
    env['PYTHONPATH'] = str(repo / 'src')

    py_files = [str(p) for p in repo.rglob('*.py') if '__pycache__' not in p.parts]
    run([sys.executable, '-m', 'py_compile', *py_files], cwd=repo, env=env)
    run([sys.executable, '-m', 'pytest', '-q'], cwd=repo, env=env)
    run([sys.executable, '-m', 'spinmesh_runtime.cli', '--mode', 'smoke', '--runtime-mode', 'local_proxy', '--output-prefix', 'release_smoke'], cwd=repo, env=env)

    try:
        import qiskit  # noqa: F401
        has_qiskit = True
    except Exception:
        has_qiskit = False

    if has_qiskit and not args.skip_aer:
        run([sys.executable, '-m', 'spinmesh_runtime.cli', '--mode', 'single', '--runtime-mode', 'aer', '--n-spins', '4', '--magnetization-m', '0', '--depth', '1', '--fourier-modes', '1', '--bo-iters', '2', '--sobol-init-iters', '1', '--spsa-iters', '2', '--random-search-iters', '2', '--classical-bo-iters', '2', '--base-shots', '32', '--output-prefix', 'release_aer'], cwd=repo, env=env)

    # cleanup validation outputs then confirm tree is clean
    subprocess.run([sys.executable, 'tools/cleanup_release.py', '--root', str(repo)], cwd=repo, env=env, check=True)
    assert_clean(repo)
    assert_release_docs(repo)
    print('Release checks passed.')


if __name__ == '__main__':
    main()
