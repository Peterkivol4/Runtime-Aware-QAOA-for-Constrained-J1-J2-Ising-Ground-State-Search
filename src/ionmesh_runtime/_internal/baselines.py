from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import RunDeck, TrialResult
from .optimization import GaussianProcessBayesOptimizer
from .problem import IsingSpinProblem


def _approximation_ratio(best_energy: float, exact_energy: float) -> float:
    scale = max(abs(float(exact_energy)), 1e-9)
    return float(1.0 + max(0.0, float(best_energy) - float(exact_energy)) / scale)


@dataclass
class SpinCandidate:
    bitstring: str
    energy: float


class ClassicalBaselines:
    def __init__(self, problem: IsingSpinProblem, cfg: RunDeck):
        self.problem = problem
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)

    def exact(self) -> SpinCandidate:
        return SpinCandidate(self.problem.exact_feasible_bitstring, self.problem.exact_feasible_energy)

    def greedy(self) -> SpinCandidate:
        bitstring, energy = self.spin_greedy()
        return SpinCandidate(bitstring, energy)

    def spin_greedy(self) -> tuple[str, float]:
        x = np.zeros(self.problem.n, dtype=int)
        assigned = np.zeros(self.problem.n, dtype=bool)
        order = np.argsort(-(np.sum(np.abs(self.problem.J), axis=1) + np.abs(self.problem.h)))
        ones_remaining = self.problem.budget

        for idx in order:
            remaining_sites = int(np.sum(~assigned))
            if ones_remaining == remaining_sites:
                x[idx] = 1
                assigned[idx] = True
                ones_remaining -= 1
                continue
            if ones_remaining == 0:
                assigned[idx] = True
                continue

            sigma = 2 * x - 1
            assigned_mask = assigned.astype(float)
            neighbor_field = float(np.dot(self.problem.J[idx], sigma * assigned_mask))
            effective_field = neighbor_field + float(self.problem.h[idx])
            assign_one = effective_field >= 0.0

            if assign_one:
                x[idx] = 1
                ones_remaining -= 1
            assigned[idx] = True

        if int(np.sum(x)) != self.problem.budget:
            bitstring = self.problem.remap_to_valid(self.problem.array_to_bitstring(x))
        else:
            bitstring = self.problem.array_to_bitstring(x)
        return bitstring, self.problem.evaluate_energy(bitstring)

    def random_search(self, iters: int = 256) -> SpinCandidate:
        best = SpinCandidate(self.problem.feasible_bitstrings[0], float("inf"))
        for _ in range(iters):
            bitstring = self.problem.feasible_bitstrings[int(self.rng.integers(len(self.problem.feasible_bitstrings)))]
            energy = self.problem.evaluate_energy(bitstring)
            if energy < best.energy:
                best = SpinCandidate(bitstring, energy)
        return best

    def local_search(self, restarts: int | None = None) -> SpinCandidate:
        restarts = restarts or self.cfg.classical_local_search_restarts
        best = self.greedy()
        for _ in range(restarts):
            current = list(best.bitstring)
            improved = True
            while improved:
                improved = False
                ones = [idx for idx, bit in enumerate(current) if bit == "1"]
                zeros = [idx for idx, bit in enumerate(current) if bit == "0"]
                for i in ones:
                    for j in zeros:
                        proposal = current.copy()
                        proposal[i], proposal[j] = "0", "1"
                        candidate = "".join(proposal)
                        energy = self.problem.evaluate_energy(candidate)
                        if energy + 1e-12 < best.energy:
                            best = SpinCandidate(candidate, energy)
                            current = proposal
                            improved = True
                            break
                    if improved:
                        break
        return best

    def simulated_annealing(self, steps: int | None = None) -> SpinCandidate:
        steps = steps or self.cfg.sa_steps
        current = list(self.greedy().bitstring)
        current_energy = self.problem.evaluate_energy("".join(current))
        best = SpinCandidate("".join(current), current_energy)
        for step in range(1, steps + 1):
            ones = [idx for idx, bit in enumerate(current) if bit == "1"]
            zeros = [idx for idx, bit in enumerate(current) if bit == "0"]
            i = int(self.rng.choice(ones))
            j = int(self.rng.choice(zeros))
            proposal = current.copy()
            proposal[i], proposal[j] = "0", "1"
            bitstring = "".join(proposal)
            energy = self.problem.evaluate_energy(bitstring)
            delta = energy - current_energy
            temperature = max(1e-3, 0.25 * (1.0 - step / steps))
            accept = delta < 0 or self.rng.random() < math.exp(-delta / temperature)
            if accept:
                current = proposal
                current_energy = energy
                if energy < best.energy:
                    best = SpinCandidate(bitstring, energy)
        return best

    def classical_bo(self, iters: int | None = None) -> SpinCandidate:
        iters = iters or self.cfg.classical_bo_iters
        optimizer = GaussianProcessBayesOptimizer(self.problem.n, min(8, max(4, iters // 3)), self.cfg.seed)
        best = SpinCandidate(self.problem.feasible_bitstrings[0], float("inf"))
        for _ in range(iters):
            logits = optimizer.suggest()
            chosen = np.argsort(logits)[-self.problem.budget :]
            bits = np.zeros(self.problem.n, dtype=int)
            bits[chosen] = 1
            bitstring = self.problem.array_to_bitstring(bits)
            energy = self.problem.evaluate_energy(bitstring)
            optimizer.observe(logits, energy)
            if energy < best.energy:
                best = SpinCandidate(bitstring, energy)
        return best

    def run_all(self) -> list[TrialResult]:
        entries: list[tuple[str, SpinCandidate]] = []
        entries.append(("exact_feasible", self.exact()))
        entries.append(("greedy", self.greedy()))
        entries.append(("local_search", self.local_search()))
        entries.append(("simulated_annealing", self.simulated_annealing()))
        entries.append(("random_search", self.random_search()))
        entries.append(("classical_bo_surrogate", self.classical_bo()))
        records: list[TrialResult] = []
        for method, candidate in entries:
            records.append(
                TrialResult(
                    method=method,
                    family="classical_baseline",
                    regime=self.problem.regime,
                    seed=self.cfg.seed,
                    n_spins=self.problem.n,
                    budget=self.problem.budget,
                    depth=self.cfg.depth,
                    noise_level=self.cfg.noise_level,
                    shot_budget=self.cfg.base_shots,
                    parameterization="classical",
                    mitigation_label="none",
                    constraint_handling="feasible",
                    best_energy=candidate.energy,
                    exact_energy=self.problem.exact_feasible_energy,
                    approximation_gap=max(0.0, candidate.energy - self.problem.exact_feasible_energy),
                    approximation_ratio=_approximation_ratio(candidate.energy, self.problem.exact_feasible_energy),
                    success=abs(candidate.energy - self.problem.exact_feasible_energy) <= self.cfg.epsilon_success,
                    valid_ratio=1.0,
                    measurement_success_probability=1.0 if abs(candidate.energy - self.problem.exact_feasible_energy) <= self.cfg.epsilon_success else 0.0,
                    runtime_seconds=0.0,
                    evaluations=0,
                    objective_calls=0,
                    total_shots=0,
                    final_bitstring=candidate.bitstring,
                    best_params=[],
                    transpilation_metadata={},
                    trace=[],
                    j2_ratio=self.cfg.j2_ratio,
                    disorder_strength=self.cfg.disorder_strength,
                    frustration_index=self.problem.frustration_index,
                    magnetization_m=self.cfg.magnetization_m,
                )
            )
        return records


__all__ = [
    "SpinCandidate",
    "ClassicalBaselines",
]
