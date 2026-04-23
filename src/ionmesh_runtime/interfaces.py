from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class QuantumRunner(ABC):
    @abstractmethod
    def evaluate_objective(self, params, penalty_state=None, *, shots=None):
        raise NotImplementedError

    @abstractmethod
    def sample_final_readout(self, params, penalty_state=None, *, shots=None):
        raise NotImplementedError

    @abstractmethod
    def execution_metadata(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def run(self, params):
        raise NotImplementedError


class RuntimeSession(ABC):
    @abstractmethod
    def ensure_open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def refresh(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def run_estimator(self, pubs: list[Any]) -> Any:
        raise NotImplementedError

    @abstractmethod
    def run_sampler(self, pubs: list[Any]) -> Any:
        raise NotImplementedError

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError


class ResultLedger(ABC):
    @abstractmethod
    def log_config(self, cfg) -> None:
        raise NotImplementedError

    @abstractmethod
    def log_records(self, records) -> None:
        raise NotImplementedError

    @abstractmethod
    def log_summary(self, summary: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_json(self, output_prefix: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    def save_csv(self, output_prefix: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    def save_sqlite(self, output_prefix: str, existing_path: str | Path | None = None) -> Path:
        raise NotImplementedError


class RuntimeGateway(ABC):
    @abstractmethod
    def handle(self, req):
        raise NotImplementedError


__all__ = [
    'QuantumRunner',
    'RuntimeSession',
    'ResultLedger',
    'RuntimeGateway',
]
