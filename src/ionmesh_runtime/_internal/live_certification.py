from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime_support import RuntimeSamplerFactory, RuntimeSessionManager, runtime_status
from .secrets import SecretsManager
from .tracking import json_dumps_clean


@dataclass
class CertificationResult:
    passed: bool
    checks: dict[str, Any]
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {'passed': self.passed, 'checks': self.checks, 'notes': self.notes}


def save_certification_report(result: CertificationResult, output_prefix: str | Path) -> tuple[Path, Path]:
    base = Path(output_prefix)
    json_path = base.with_suffix('.json')
    md_path = base.with_suffix('.md')
    json_path.write_text(json_dumps_clean(result.as_dict(), indent=2))

    lines = [
        '# Live IBM Hardware Certification Report',
        '',
        f'- passed: **{result.passed}**',
        '',
        '## Checks',
    ]
    for key, value in result.checks.items():
        lines.append(f'- **{key}**: {value}')
    lines.extend(['', '## Notes'])
    for note in result.notes:
        lines.append(f'- {note}')
    md_path.write_text('\n'.join(lines) + '\n')
    return json_path, md_path


def run_live_certification_check(cfg: Any, *, backend_name: str | None = None) -> CertificationResult:
    status = runtime_status()
    checks: dict[str, Any] = {
        'runtime_available': status.available,
        'status_message': status.message,
        'runtime_secret_presence': SecretsManager.runtime_presence(),
    }
    if not status.available:
        return CertificationResult(False, checks, ['Runtime dependencies are not installed.'])

    service = RuntimeSamplerFactory.create_service(cfg, strict=True)
    backend = RuntimeSamplerFactory.select_backend(service, backend_name)
    backend_status = backend.status()
    checks.update(
        {
            'backend_name': getattr(backend, 'name', lambda: str(backend))() if callable(getattr(backend, 'name', None)) else getattr(backend, 'name', str(backend)),
            'backend_operational': getattr(backend_status, 'operational', None),
            'backend_pending_jobs': getattr(backend_status, 'pending_jobs', None),
            'simulator': getattr(backend.configuration(), 'simulator', False) if hasattr(backend, 'configuration') else False,
        }
    )

    mgr = RuntimeSessionManager(cfg, backend, open_context=False)
    checks['selected_execution_mode'] = mgr.plan.selected_mode
    checks['selection_reason'] = mgr.plan.selection_reason

    notes = [
        'This is a preflight only. It checks readiness without opening a live Runtime context or burning session budget.',
        'Run a real EstimatorV2/SamplerV2 workload after this and save session/job IDs with the outputs.',
        'Do not claim live certification until checkpointed resume works cleanly across a real session boundary.',
    ]
    passed = bool(
        checks.get('backend_operational') and not checks.get('simulator') and mgr.plan.selected_mode in {'session', 'batch', 'backend'}
    )
    return CertificationResult(passed, checks, notes)

__all__ = [
    'CertificationResult',
    'save_certification_report',
    'run_live_certification_check',
]
