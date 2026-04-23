from __future__ import annotations

from itertools import combinations
from typing import Iterable

import numpy as np

from .config import ConstraintPenaltyState, RunDeck


class IsingSpinProblem:
    def __init__(
        self,
        cfg: RunDeck,
        *,
        seed: int | None = None,
        lattice_type: str | None = None,
        J: np.ndarray | None = None,
        h: np.ndarray | None = None,
    ):
        self.cfg = cfg
        self.n = cfg.n_spins
        self.budget = cfg.budget
        self.magnetization_m = cfg.magnetization_m
        self.lattice_type = lattice_type or cfg.lattice_type
        self.regime = self.lattice_type
        self.seed = cfg.seed if seed is None else seed
        self.rng = np.random.default_rng(self.seed)
        self.rows, self.cols = self._lattice_shape(self.n)
        self.nn_edges = self._nearest_neighbor_edges()
        self.nnn_edges = self._next_nearest_neighbor_edges()
        if J is not None or h is not None:
            if J is None or h is None:
                raise ValueError("Both J and h must be provided together.")
            self.J = np.asarray(J, dtype=float).copy()
            self.h = np.asarray(h, dtype=float).copy()
            if self.J.shape != (self.n, self.n):
                raise ValueError(f"J must have shape {(self.n, self.n)}.")
            if self.h.shape != (self.n,):
                raise ValueError(f"h must have shape {(self.n,)}.")
            self.J = 0.5 * (self.J + self.J.T)
            np.fill_diagonal(self.J, 0.0)
        else:
            self.J, self.h = self._generate_couplings(self.lattice_type)
        self.Q = self._to_qubo(self.J, self.h)
        self.qubo_constant = self._qubo_constant(self.J, self.h)
        self.feasible_bitstrings = self._enumerate_feasible_bitstrings()
        self.exact_feasible_bitstring, self.exact_feasible_energy = self._exact_feasible_optimum()
        self.energy_gap_to_second_lowest = self._energy_gap()
        self.frustration_index = self._compute_frustration()
        self.lattice_metadata = {
            "source": "synthetic_lattice",
            "lattice_type": self.lattice_type,
            "rows": self.rows,
            "cols": self.cols,
            "nearest_neighbor_edges": len(self.nn_edges),
            "next_nearest_neighbor_edges": len(self.nnn_edges),
            "j2_ratio": self.cfg.j2_ratio,
            "disorder_strength": self.cfg.disorder_strength,
            "bond_dilution_prob": self.cfg.bond_dilution_prob,
            "magnetization_m": self.magnetization_m,
        }

    @staticmethod
    def _lattice_shape(n_spins: int) -> tuple[int, int]:
        rows = int(np.floor(np.sqrt(n_spins)))
        while rows > 1 and n_spins % rows != 0:
            rows -= 1
        cols = n_spins // rows
        return rows, cols

    def _index(self, row: int, col: int) -> int:
        return row * self.cols + col

    def _nearest_neighbor_edges(self) -> list[tuple[int, int]]:
        edges: list[tuple[int, int]] = []
        for row in range(self.rows):
            for col in range(self.cols):
                current = self._index(row, col)
                if col + 1 < self.cols:
                    edges.append((current, self._index(row, col + 1)))
                if row + 1 < self.rows:
                    edges.append((current, self._index(row + 1, col)))
        return edges

    def _next_nearest_neighbor_edges(self) -> list[tuple[int, int]]:
        edges: list[tuple[int, int]] = []
        for row in range(self.rows - 1):
            for col in range(self.cols - 1):
                edges.append((self._index(row, col), self._index(row + 1, col + 1)))
                edges.append((self._index(row, col + 1), self._index(row + 1, col)))
        return edges

    def _sublattice_sign(self, index: int) -> int:
        row, col = divmod(index, self.cols)
        return 1 if (row + col) % 2 == 0 else -1

    def _perturb(self, base: float) -> float:
        if abs(base) <= 1e-12 or self.cfg.disorder_strength <= 0.0:
            return float(base)
        scale = 1.0 + float(self.rng.uniform(-self.cfg.disorder_strength, self.cfg.disorder_strength))
        return float(base * scale)

    def _assign_edge(self, J: np.ndarray, i: int, j: int, value: float) -> None:
        J[i, j] = value
        J[j, i] = value

    def _generate_couplings(self, lattice_type: str) -> tuple[np.ndarray, np.ndarray]:
        J = np.zeros((self.n, self.n), dtype=float)
        h = np.full(self.n, float(self.cfg.h_field), dtype=float)
        j1 = float(abs(self.cfg.j1_coupling))
        j2 = float(abs(self.cfg.j2_coupling))

        if lattice_type == "random_bond":
            for i, j in self.nn_edges:
                self._assign_edge(J, i, j, float(self.rng.uniform(-j1, j1)))
            for i, j in self.nnn_edges:
                self._assign_edge(J, i, j, float(self.rng.uniform(-max(j2, 1e-9), max(j2, 1e-9))))
            if self.cfg.disorder_strength > 0.0:
                h += self.rng.uniform(-self.cfg.disorder_strength, self.cfg.disorder_strength, size=self.n)
        elif lattice_type == "afm_uniform":
            for i, j in self.nn_edges:
                self._assign_edge(J, i, j, self._perturb(-j1))
            for i, j in self.nnn_edges:
                self._assign_edge(J, i, j, self._perturb(-j2))
        elif lattice_type == "j1j2_frustrated":
            for i, j in self.nn_edges:
                self._assign_edge(J, i, j, self._perturb(-j1))
            for i, j in self.nnn_edges:
                self._assign_edge(J, i, j, self._perturb(-j2))
        elif lattice_type == "diluted":
            for edge_list, scale in ((self.nn_edges, j1), (self.nnn_edges, j2)):
                for i, j in edge_list:
                    keep = self.rng.random() >= self.cfg.bond_dilution_prob
                    value = float(self.rng.uniform(-max(scale, 1e-9), max(scale, 1e-9))) if keep else 0.0
                    self._assign_edge(J, i, j, value)
            if self.cfg.disorder_strength > 0.0:
                h += self.rng.uniform(-self.cfg.disorder_strength, self.cfg.disorder_strength, size=self.n)
        elif lattice_type == "random_ferrimagnet":
            for i in range(self.n):
                h[i] += self._sublattice_sign(i) * self.cfg.disorder_strength
            for i, j in self.nn_edges:
                same = self._sublattice_sign(i) == self._sublattice_sign(j)
                base = j1 if same else -j1
                self._assign_edge(J, i, j, self._perturb(base))
            for i, j in self.nnn_edges:
                self._assign_edge(J, i, j, self._perturb(j2))
        else:  # pragma: no cover - guarded by config validation
            raise ValueError(f"Unknown lattice_type: {lattice_type}")

        return J, h

    def _to_qubo(self, J: np.ndarray, h: np.ndarray) -> np.ndarray:
        Q = np.zeros((self.n, self.n), dtype=float)
        for i in range(self.n):
            Q[i, i] = float(2.0 * np.sum(J[i]) - 2.0 * h[i])
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if abs(J[i, j]) <= 1e-12:
                    continue
                Q[i, j] = float(-4.0 * J[i, j])
        return Q

    def _qubo_constant(self, J: np.ndarray, h: np.ndarray) -> float:
        return float(-np.sum(np.triu(J, 1)) + np.sum(h))

    def _enumerate_feasible_bitstrings(self) -> list[str]:
        bitstrings: list[str] = []
        for chosen in combinations(range(self.n), self.budget):
            bits = np.zeros(self.n, dtype=int)
            bits[list(chosen)] = 1
            bitstrings.append(self.array_to_bitstring(bits))
        return bitstrings

    def _exact_feasible_optimum(self) -> tuple[str, float]:
        best_energy = float("inf")
        best_bitstring = self.feasible_bitstrings[0]
        for bitstring in self.feasible_bitstrings:
            energy = self.evaluate_energy(bitstring)
            if energy < best_energy:
                best_energy = energy
                best_bitstring = bitstring
        return best_bitstring, float(best_energy)

    def _energy_gap(self) -> float | None:
        if len(self.feasible_bitstrings) < 2:
            return None
        values = sorted({float(self.evaluate_energy(bitstring)) for bitstring in self.feasible_bitstrings})
        if len(values) < 2:
            return 0.0
        return float(values[1] - values[0])

    def _compute_frustration(self) -> float:
        plaquettes = 0
        frustrated = 0
        for row in range(self.rows - 1):
            for col in range(self.cols - 1):
                tl = self._index(row, col)
                tr = self._index(row, col + 1)
                bl = self._index(row + 1, col)
                br = self._index(row + 1, col + 1)
                bonds = [
                    (tl, tr, self.J[tl, tr]),
                    (tr, br, self.J[tr, br]),
                    (bl, br, self.J[bl, br]),
                    (tl, bl, self.J[tl, bl]),
                    (tl, br, self.J[tl, br]),
                    (tr, bl, self.J[tr, bl]),
                ]
                active = [(i, j, value) for i, j, value in bonds if abs(value) > 1e-12]
                local_bound = -sum(abs(value) for _, _, value in active)
                local_min = float("inf")
                for state_index in range(16):
                    local_spins = {
                        tl: 1 if state_index & 1 else -1,
                        tr: 1 if state_index & 2 else -1,
                        bl: 1 if state_index & 4 else -1,
                        br: 1 if state_index & 8 else -1,
                    }
                    energy = -sum(value * local_spins[i] * local_spins[j] for i, j, value in active)
                    local_min = min(local_min, float(energy))
                if local_min > local_bound + 1e-9:
                    frustrated += 1
                plaquettes += 1
        if plaquettes == 0:
            return float("nan")
        return float(frustrated / plaquettes)

    def bitstring_to_array(self, bitstring: str) -> np.ndarray:
        return np.fromiter((int(bit) for bit in bitstring), dtype=int)

    def array_to_bitstring(self, bits: np.ndarray | list[int]) -> str:
        return "".join(str(int(bit)) for bit in bits)

    def bitstring_to_spins(self, bitstring: str) -> np.ndarray:
        return 2 * self.bitstring_to_array(bitstring) - 1

    def evaluate_ising_energy(self, bitstring: str) -> float:
        sigma = self.bitstring_to_spins(bitstring).astype(float)
        pair_term = -sum(self.J[i, j] * sigma[i] * sigma[j] for i in range(self.n) for j in range(i + 1, self.n))
        field_term = -float(self.h @ sigma)
        return float(pair_term + field_term)

    def violation(self, bitstring: str) -> float:
        x = self.bitstring_to_array(bitstring)
        return float(abs(np.sum(x) - self.budget))

    def evaluate_energy(
        self,
        bitstring: str,
        *,
        penalize_invalid: bool = False,
        penalty_strength: float | None = None,
        penalty_linear: float = 0.0,
        penalty_state: ConstraintPenaltyState | None = None,
    ) -> float:
        x = self.bitstring_to_array(bitstring)
        pair_terms = float(np.sum(np.triu(self.Q, 1) * np.outer(x, x)))
        linear_terms = float(np.dot(np.diag(self.Q), x))
        energy = float(linear_terms + pair_terms + self.qubo_constant)
        if penalize_invalid and not self.is_valid(bitstring):
            violation = self.violation(bitstring)
            if penalty_state is not None:
                linear = penalty_state.linear_strength
                quadratic = penalty_state.quadratic_strength
            else:
                linear = penalty_linear
                quadratic = self.cfg.penalty_strength if penalty_strength is None else penalty_strength
            energy += linear * violation + quadratic * (violation**2)
        return energy

    def is_valid(self, bitstring: str) -> bool:
        return bitstring.count("1") == self.budget

    def remap_to_valid(self, bitstring: str) -> str:
        if self.is_valid(bitstring):
            return bitstring

        bits = self.bitstring_to_array(bitstring)
        while int(bits.sum()) > self.budget:
            candidates: list[tuple[float, int]] = []
            for idx in np.flatnonzero(bits):
                proposal = bits.copy()
                proposal[idx] = 0
                candidates.append((self.evaluate_energy(self.array_to_bitstring(proposal)), int(idx)))
            _, best_idx = min(candidates, key=lambda item: (item[0], item[1]))
            bits[best_idx] = 0
        while int(bits.sum()) < self.budget:
            candidates = []
            for idx in np.flatnonzero(bits == 0):
                proposal = bits.copy()
                proposal[idx] = 1
                candidates.append((self.evaluate_energy(self.array_to_bitstring(proposal)), int(idx)))
            _, best_idx = min(candidates, key=lambda item: (item[0], item[1]))
            bits[best_idx] = 1
        return self.array_to_bitstring(bits)

    def all_bitstrings(self) -> Iterable[str]:
        for index in range(2**self.n):
            yield format(index, f"0{self.n}b")

    def greedy_solution(self) -> tuple[str, float]:
        bits = np.zeros(self.n, dtype=int)
        chosen: set[int] = set()
        while len(chosen) < self.budget:
            best_idx = None
            best_energy = float("inf")
            for idx in range(self.n):
                if idx in chosen:
                    continue
                proposal = bits.copy()
                proposal[idx] = 1
                energy = self.evaluate_energy(self.array_to_bitstring(proposal))
                if energy < best_energy:
                    best_energy = energy
                    best_idx = idx
            assert best_idx is not None
            bits[best_idx] = 1
            chosen.add(best_idx)
        bitstring = self.array_to_bitstring(bits)
        return bitstring, self.evaluate_energy(bitstring)


PortfolioProblem = IsingSpinProblem


__all__ = [
    "IsingSpinProblem",
    "PortfolioProblem",
]
