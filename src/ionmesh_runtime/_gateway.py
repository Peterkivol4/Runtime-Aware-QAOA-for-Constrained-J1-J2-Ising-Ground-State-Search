from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .interfaces import RuntimeGateway
from ._internal.config import RunDeck as RelayPlan
from ._internal.pipeline import run_benchmark_study, run_decision, run_single_benchmark


@dataclass
class MeshEnvelope:
    mode: str = "decision"
    config: dict[str, Any] | None = None


@dataclass
class MeshReply:
    status: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "payload": self.payload}


class MeshRuntime(RuntimeGateway):
    def handle(self, req: MeshEnvelope) -> MeshReply:
        cfg = RelayPlan(**(req.config or {}))
        cfg.validate()

        if req.mode == "single":
            res = run_single_benchmark(cfg)
        elif req.mode == "study":
            res = run_benchmark_study(cfg)
        else:
            res = run_decision(cfg)

        payload = {"result": res, "config": asdict(cfg), "mode": req.mode}
        return MeshReply(status="ok", payload=payload)


__all__ = ['RelayPlan', 'MeshEnvelope', 'MeshReply', 'MeshRuntime']
