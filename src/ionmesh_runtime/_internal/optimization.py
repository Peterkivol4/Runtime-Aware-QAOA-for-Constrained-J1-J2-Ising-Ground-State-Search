from __future__ import annotations

from dataclasses import dataclass
import warnings
from typing import Any

import numpy as np

from .optional_deps import load_gp_tools, load_sobol_tools

__all__ = [
    'project_params',
    'GaussianProcessBayesOptimizer',
    'spsa_step',
    'fourier_to_physical',
]


def project_params(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return ((x + np.pi) % (2.0 * np.pi)) - np.pi


@dataclass
class GaussianProcessBayesOptimizer:
    n_params: int
    n_init: int
    seed: int
    lower_bound: float = -np.pi
    upper_bound: float = np.pi
    context_dim: int = 0

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)
        self.train_x: list[np.ndarray] = []
        self.train_y: list[float] = []
        qmc = load_sobol_tools()
        sampler = qmc.Sobol(d=self.n_params, scramble=True, seed=self.seed)
        sobol = sampler.random_base2(m=int(np.ceil(np.log2(max(2, self.n_init)))))
        sobol = sobol[: self.n_init]
        self.initial_pool = qmc.scale(sobol, self.lower_bound, self.upper_bound)

    @property
    def model_dim(self) -> int:
        return self.n_params + self.context_dim

    def _context_array(self, context: np.ndarray | None) -> np.ndarray:
        if self.context_dim == 0:
            return np.zeros(0, dtype=float)
        if context is None:
            return np.zeros(self.context_dim, dtype=float)
        context = np.asarray(context, dtype=float).reshape(-1)
        if context.size != self.context_dim:
            raise ValueError(f"Expected context dimension {self.context_dim}, received {context.size}.")
        return context

    def _join(self, params: np.ndarray, context: np.ndarray | None) -> np.ndarray:
        params = project_params(np.asarray(params, dtype=float).reshape(-1))
        ctx = self._context_array(context)
        if ctx.size == 0:
            return params
        return np.concatenate([params, ctx])

    def _build_gp(self):
        gp_tools = load_gp_tools()
        ConstantKernel = gp_tools["ConstantKernel"]
        Matern = gp_tools["Matern"]
        WhiteKernel = gp_tools["WhiteKernel"]
        GaussianProcessRegressor = gp_tools["GaussianProcessRegressor"]
        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(length_scale=np.ones(self.model_dim), nu=2.5) + WhiteKernel(
            noise_level=1e-4, noise_level_bounds=(1e-8, 1e-1)
        )
        return GaussianProcessRegressor(kernel=kernel, normalize_y=True, random_state=self.seed, n_restarts_optimizer=2)

    def suggest(self, context: np.ndarray | None = None) -> np.ndarray:
        if len(self.train_x) < self.n_init:
            return self.initial_pool[len(self.train_x)].copy()
        gp_tools = load_gp_tools()
        ConvergenceWarning = gp_tools["ConvergenceWarning"]
        x = np.vstack(self.train_x)
        y = np.asarray(self.train_y, dtype=float)
        gp = self._build_gp()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            gp.fit(x, y)
        best_index = int(np.argmin(y))
        center = x[best_index][: self.n_params]
        radius = np.pi / 2.0
        candidates = self.rng.uniform(self.lower_bound, self.upper_bound, size=(512, self.n_params))
        local = center + self.rng.normal(scale=radius / 2.0, size=(512, self.n_params))
        local = np.clip(local, self.lower_bound, self.upper_bound)
        pool_params = np.vstack([candidates, local])
        ctx = self._context_array(context)
        if ctx.size:
            pool = np.hstack([pool_params, np.tile(ctx, (pool_params.shape[0], 1))])
        else:
            pool = pool_params
        mean, std = gp.predict(pool, return_std=True)
        acquisition = mean - 1.5 * std
        return pool_params[int(np.argmin(acquisition))]

    def observe(self, x: np.ndarray, y: float, context: np.ndarray | None = None) -> None:
        self.train_x.append(self._join(x, context))
        self.train_y.append(float(y))

    def incumbent(self) -> np.ndarray | None:
        if not self.train_x:
            return None
        idx = int(np.argmin(np.asarray(self.train_y, dtype=float)))
        return np.asarray(self.train_x[idx][: self.n_params], dtype=float).copy()

    def best_points(self, limit: int = 2) -> list[np.ndarray]:
        if not self.train_x:
            return []
        order = np.argsort(np.asarray(self.train_y, dtype=float))[: max(0, limit)]
        return [np.asarray(self.train_x[int(idx)][: self.n_params], dtype=float).copy() for idx in order]

    def restart_around(self, incumbent: np.ndarray | None = None, jitter_scale: float = 0.2) -> None:
        self.train_x.clear()
        self.train_y.clear()
        if incumbent is None:
            return
        incumbent = project_params(np.asarray(incumbent, dtype=float).reshape(-1))
        warm = [incumbent]
        for _ in range(max(0, self.n_init - 1)):
            warm.append(project_params(incumbent + self.rng.normal(scale=jitter_scale, size=incumbent.shape)))
        self.initial_pool = np.vstack(warm)

    def start_new_epoch(
        self,
        *,
        strategy: str,
        incumbent: np.ndarray | None = None,
        warmstart_points: int = 2,
        penalty_context: np.ndarray | None = None,
    ) -> None:
        if strategy == "contextual":
            return
        keep_points = self.best_points(limit=max(0, warmstart_points))
        self.train_x.clear()
        self.train_y.clear()
        seed_points: list[np.ndarray] = []
        if incumbent is not None:
            seed_points.append(project_params(np.asarray(incumbent, dtype=float).reshape(-1)))
        for point in keep_points:
            if len(seed_points) >= self.n_init:
                break
            seed_points.append(project_params(point))
        while len(seed_points) < self.n_init and seed_points:
            seed_points.append(project_params(seed_points[0] + self.rng.normal(scale=0.15, size=seed_points[0].shape)))
        if seed_points:
            self.initial_pool = np.vstack(seed_points[: self.n_init])
        elif incumbent is not None:
            self.restart_around(incumbent)

    def state_dict(self) -> dict[str, Any]:
        return {
            "n_params": int(self.n_params),
            "n_init": int(self.n_init),
            "seed": int(self.seed),
            "lower_bound": float(self.lower_bound),
            "upper_bound": float(self.upper_bound),
            "context_dim": int(self.context_dim),
            "train_x": [x.tolist() for x in self.train_x],
            "train_y": [float(y) for y in self.train_y],
            "initial_pool": np.asarray(self.initial_pool, dtype=float).tolist(),
            "rng_state": self.rng.bit_generator.state,
        }

    @classmethod
    def from_state_dict(cls, payload: dict[str, Any]) -> "GaussianProcessBayesOptimizer":
        optimizer = cls(
            n_params=int(payload["n_params"]),
            n_init=int(payload["n_init"]),
            seed=int(payload["seed"]),
            lower_bound=float(payload.get("lower_bound", -np.pi)),
            upper_bound=float(payload.get("upper_bound", np.pi)),
            context_dim=int(payload.get("context_dim", 0)),
        )
        optimizer.train_x = [np.asarray(x, dtype=float) for x in payload.get("train_x", [])]
        optimizer.train_y = [float(y) for y in payload.get("train_y", [])]
        if "initial_pool" in payload:
            optimizer.initial_pool = np.asarray(payload["initial_pool"], dtype=float)
        if payload.get("rng_state") is not None:
            optimizer.rng.bit_generator.state = payload["rng_state"]
        return optimizer


def spsa_step(x: np.ndarray, value_fn, step_size: float, perturb_scale: float, rng: np.random.Generator) -> tuple[np.ndarray, float]:
    delta = rng.choice([-1.0, 1.0], size=x.shape)
    plus = project_params(x + perturb_scale * delta)
    minus = project_params(x - perturb_scale * delta)
    value_plus = float(value_fn(plus))
    value_minus = float(value_fn(minus))
    grad = ((value_plus - value_minus) / (2.0 * perturb_scale)) * delta
    updated = project_params(x - step_size * grad)
    return updated, min(value_plus, value_minus)


def fourier_to_physical(params: np.ndarray, depth: int, fourier_modes: int) -> np.ndarray:
    params = np.asarray(params, dtype=float)
    a_coeffs = params[:fourier_modes]
    b_coeffs = params[fourier_modes:]
    gamma_values = np.zeros(depth)
    beta_values = np.zeros(depth)
    for depth_idx in range(depth):
        layer = depth_idx + 1
        for mode in range(fourier_modes):
            frequency = (mode + 0.5) * layer * np.pi / depth
            gamma_values[depth_idx] += a_coeffs[mode] * np.sin(frequency)
            beta_values[depth_idx] += b_coeffs[mode] * np.sin(frequency)
    return np.concatenate([gamma_values, beta_values])
