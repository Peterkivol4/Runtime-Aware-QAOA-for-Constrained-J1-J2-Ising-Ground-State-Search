from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ionmesh_runtime.interfaces import RuntimeGateway
from .config import RunDeck
from .pipeline import run_benchmark_study, run_decision, run_single_benchmark


@dataclass
class InternalServiceEnvelope:
    mode: str = "decision"
    config: dict[str, Any] | None = None


@dataclass
class InternalServiceReply:
    status: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "payload": self.payload}


class InternalSpinRuntime(RuntimeGateway):
    def handle(self, req: InternalServiceEnvelope) -> InternalServiceReply:
        cfg = RunDeck(**(req.config or {}))
        cfg.validate()

        if req.mode == "single":
            res = run_single_benchmark(cfg)
        elif req.mode == "study":
            res = run_benchmark_study(cfg)
        else:
            res = run_decision(cfg)

        payload = {"result": res, "config": asdict(cfg), "mode": req.mode}
        return InternalServiceReply(status="ok", payload=payload)


__all__ = [
    'InternalServiceEnvelope',
    'InternalServiceReply',
    'InternalSpinRuntime',
]
