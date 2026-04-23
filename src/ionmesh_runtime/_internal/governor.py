from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import RunDeck, TailBatch


@dataclass
class ShotBudgetGovernor:
    cfg: RunDeck
    total_steps: int
    cumulative_shots: int = 0
    current_shots: int = 0
    stagnant_steps: int = 0
    last_best_energy: float = float("inf")
    stop_reason: str | None = None
    decisions: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.current_shots = int(self.cfg.dynamic_shots)

    @property
    def budget_cap(self) -> int:
        explicit = getattr(self.cfg, "shot_governor_max_cumulative_shots", None)
        if explicit is not None:
            return int(explicit)
        return int(self.total_steps * self.cfg.dynamic_shots * self.cfg.shot_governor_budget_multiplier)

    def next_shots(self, evaluation: int) -> int:
        if not self.cfg.shot_governor_enabled:
            return int(self.cfg.dynamic_shots)
        remaining = max(0, self.budget_cap - self.cumulative_shots)
        proposed = min(self.current_shots, remaining if remaining > 0 else self.current_shots)
        proposed = max(self.cfg.shot_governor_min_shots, proposed)
        proposed = min(self.cfg.shot_governor_max_shots, proposed)
        self.decisions.append({"evaluation": int(evaluation), "planned_shots": int(proposed), "cumulative_shots": int(self.cumulative_shots)})
        return int(proposed)

    def observe(self, evaluation: int, batch: TailBatch, best_energy: float) -> None:
        self.cumulative_shots += int(batch.total_shots)
        improvement = 0.0 if self.last_best_energy == float("inf") else max(0.0, self.last_best_energy - best_energy)
        if improvement < self.cfg.shot_governor_min_improvement:
            self.stagnant_steps += 1
        else:
            self.stagnant_steps = 0
        self.last_best_energy = min(self.last_best_energy, best_energy)

        decision: dict[str, Any] = {
            "evaluation": int(evaluation),
            "used_shots": int(batch.total_shots),
            "cumulative_shots": int(self.cumulative_shots),
            "best_energy": float(best_energy),
            "valid_ratio": float(batch.valid_ratio),
            "improvement": float(improvement),
        }

        if self.cumulative_shots >= self.budget_cap:
            self.stop_reason = "shot_budget_exhausted"
            decision["action"] = self.stop_reason
        elif self.stagnant_steps >= self.cfg.shot_governor_patience:
            if self.current_shots < self.cfg.shot_governor_max_shots and batch.valid_ratio < 0.8:
                boosted = int(round(self.current_shots * self.cfg.shot_governor_escalation))
                self.current_shots = max(self.current_shots + 1, min(self.cfg.shot_governor_max_shots, boosted))
                decision["action"] = "escalate_shots"
                decision["next_shots"] = int(self.current_shots)
                self.stagnant_steps = 0
            else:
                self.stop_reason = "marginal_gain_exhausted"
                decision["action"] = self.stop_reason
        else:
            decision["action"] = "continue"
        self.decisions.append(decision)

    def should_stop(self) -> bool:
        return self.stop_reason is not None

    def final_readout_shots(self) -> int:
        if not self.cfg.shot_governor_enabled:
            return int(self.cfg.dynamic_shots)
        remaining = max(self.cfg.shot_governor_min_shots, self.budget_cap - self.cumulative_shots)
        return int(min(max(self.current_shots, self.cfg.shot_governor_min_shots), remaining, self.cfg.shot_governor_max_shots))

    def metadata(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.cfg.shot_governor_enabled),
            "budget_cap": int(self.budget_cap),
            "cumulative_shots": int(self.cumulative_shots),
            "stop_reason": self.stop_reason,
            "decisions": self.decisions,
        }

__all__ = [
    'ShotBudgetGovernor',
]
