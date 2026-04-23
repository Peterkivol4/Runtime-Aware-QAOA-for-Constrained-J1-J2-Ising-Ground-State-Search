from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .constants import DEFAULT_RUNTIME_MESSAGES, RUNTIME_SECRET_ENV
from .secure_buffer import SecureBuffer
from .safe_errors import safe_error


@dataclass(frozen=True)
class RuntimeSecrets:
    channel: str | None = None
    token: SecureBuffer | None = None
    instance: str | None = None
    url: str | None = None

    def service_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.channel:
            payload['channel'] = self.channel
        if self.token:
            payload['token'] = self.token.to_text()
        if self.instance:
            payload['instance'] = self.instance
        if self.url:
            payload['url'] = self.url
        return payload

    def required_present(self) -> bool:
        return bool(self.channel and self.token)


class SecretsManager:
    @staticmethod
    def _read_aliases(*names: str) -> str | None:
        for name in names:
            value = os.getenv(name)
            if value:
                return value
        return None

    @classmethod
    def runtime(cls, *, strict: bool = False) -> RuntimeSecrets:
        token = cls._read_aliases(*RUNTIME_SECRET_ENV['token'])
        payload = RuntimeSecrets(
            channel=cls._read_aliases(*RUNTIME_SECRET_ENV['channel']),
            token=SecureBuffer(token) if token else None,
            instance=cls._read_aliases(*RUNTIME_SECRET_ENV['instance']),
            url=cls._read_aliases(*RUNTIME_SECRET_ENV['url']),
        )
        if strict and not payload.required_present():
            raise safe_error('IM-SEC-001', DEFAULT_RUNTIME_MESSAGES['missing_credentials'])
        return payload

    @classmethod
    def runtime_presence(cls) -> dict[str, bool]:
        payload = cls.runtime(strict=False)
        return {
            'channel': bool(payload.channel),
            'token': bool(payload.token),
            'instance': bool(payload.instance),
            'url': bool(payload.url),
        }


__all__ = ['SecureBuffer', 'RuntimeSecrets', 'SecretsManager']
