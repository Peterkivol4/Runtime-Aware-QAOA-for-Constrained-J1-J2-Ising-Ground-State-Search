from __future__ import annotations

from typing import Any

import numpy as np

try:  # pragma: no cover - optional native path
    from . import _kernels
except Exception:  # pragma: no cover - optional native path
    _kernels = None

__all__ = ["distribution_stats", "native_enabled", "weighted_cvar"]


def native_enabled() -> bool:
    return _kernels is not None


def weighted_cvar(energies: Any, weights: Any, alpha: float) -> tuple[float, float, float]:
    energies_arr = np.ascontiguousarray(np.asarray(energies, dtype=np.float64))
    weights_arr = np.ascontiguousarray(np.asarray(weights, dtype=np.float64))
    if energies_arr.size == 0:
        return 1e9, 1.0, 1e9
    if _kernels is not None:
        return tuple(float(v) for v in _kernels.weighted_cvar(energies_arr, weights_arr, float(alpha)))
    order = np.argsort(energies_arr)[::-1]
    ordered_energies = energies_arr[order]
    ordered_weights = weights_arr[order]
    total_weight = float(np.sum(ordered_weights))
    if total_weight <= 0.0:
        return 1e9, 1.0, 1e9
    target_weight = max(float(alpha) * total_weight, 1e-12)
    cumulative = 0.0
    sum1 = 0.0
    sum2 = 0.0
    feasible_best = float(np.min(energies_arr))
    for energy, weight in zip(ordered_energies, ordered_weights):
        share = min(float(weight), target_weight - cumulative)
        if share <= 0.0:
            break
        cumulative += share
        sum1 += float(energy) * share
        sum2 += float(energy) * float(energy) * share
        if cumulative >= target_weight:
            break
    mean = sum1 / max(cumulative, 1e-12)
    second = sum2 / max(cumulative, 1e-12)
    variance = max(1e-12, second - mean * mean)
    return float(mean), float(variance), feasible_best


def distribution_stats(base_energies: Any, weights: Any, valid_mask: Any, success_mask: Any | None = None) -> tuple[float, float, float, float, float]:
    base_arr = np.ascontiguousarray(np.asarray(base_energies, dtype=np.float64))
    weight_arr = np.ascontiguousarray(np.asarray(weights, dtype=np.float64))
    valid_arr = np.ascontiguousarray(np.asarray(valid_mask, dtype=np.uint8))
    if success_mask is None:
        success_arr = np.zeros(base_arr.shape[0], dtype=np.uint8)
    else:
        success_arr = np.ascontiguousarray(np.asarray(success_mask, dtype=np.uint8))
    if _kernels is not None:
        return tuple(float(v) for v in _kernels.distribution_stats(base_arr, weight_arr, valid_arr, success_arr))
    total_weight = float(np.sum(weight_arr))
    if total_weight <= 0.0:
        return 1e9, 1e9, 0.0, 0.0, 0.0
    observed = weight_arr > 0.0
    raw_best = float(np.min(base_arr[observed])) if np.any(observed) else 1e9
    feasible_obs = observed & (valid_arr > 0)
    feasible_best = float(np.min(base_arr[feasible_obs])) if np.any(feasible_obs) else 1e9
    valid_weight = float(np.sum(weight_arr[valid_arr > 0]))
    success_weight = float(np.sum(weight_arr[success_arr > 0]))
    return raw_best, feasible_best, valid_weight, success_weight, total_weight
