from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SafeErrorSpec:
    code: str
    operator_message: str
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'code': self.code,
            'operator_message': self.operator_message,
            'detail': self.detail,
        }


def debug_mode() -> bool:
    return os.getenv('IONMESH_DEBUG_ERRORS', '').strip().lower() in {'1', 'true', 'yes', 'on'}


def safe_error(code: str, operator_message: str, *, detail: str | None = None) -> RuntimeError:
    if debug_mode() and detail:
        return RuntimeError(f'[{code}] {operator_message} :: {detail}')
    return RuntimeError(f'[{code}] {operator_message}')


__all__ = ['SafeErrorSpec', 'debug_mode', 'safe_error']
