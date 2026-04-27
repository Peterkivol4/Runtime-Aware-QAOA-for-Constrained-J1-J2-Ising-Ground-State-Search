from __future__ import annotations

import pandas as pd

from spinmesh_runtime.config import RunDeck
from spinmesh_runtime.decision import build_decision_report, compute_utility_frontier
from spinmesh_runtime.governor import ShotBudgetGovernor
from spinmesh_runtime.pipeline import run_single_benchmark


def test_spin_problem_single_benchmark_payload() -> None:
    cfg = RunDeck(
        lattice_type="j1j2_frustrated",
        j2_coupling=0.5,
        n_spins=4,
        magnetization_m=0,
        depth=1,
        fourier_modes=1,
        bo_iters=2,
        sobol_init_iters=1,
        spsa_iters=2,
        random_search_iters=2,
        classical_bo_iters=2,
        base_shots=16,
        runtime_mode="local_proxy",
    )
    result = run_single_benchmark(cfg)
    assert result["problem"]["lattice_type"] == "j1j2_frustrated"
    assert result["problem"]["lattice_metadata"]["source"] == "synthetic_lattice"
    assert "J" in result["problem"]
    assert "h" in result["problem"]


def test_decision_report_and_governor_metadata(tmp_path: Path) -> None:
    cfg = RunDeck(
        n_spins=4,
        magnetization_m=0,
        depth=1,
        fourier_modes=1,
        bo_iters=2,
        sobol_init_iters=1,
        spsa_iters=2,
        random_search_iters=2,
        classical_bo_iters=2,
        base_shots=16,
        runtime_mode="local_proxy",
        output_prefix=str(tmp_path / "single"),
    )
    result = run_single_benchmark(cfg)
    frame = pd.DataFrame(result["records"])
    frontier = compute_utility_frontier(frame, cfg)
    decision = build_decision_report(frame, cfg)
    assert not frontier.empty
    assert "recommendation" in decision

    governor = ShotBudgetGovernor(cfg, total_steps=5)
    assert governor.next_shots(1) >= cfg.shot_governor_min_shots


def test_decision_report_handles_empty_input() -> None:
    cfg = RunDeck()
    empty = pd.DataFrame()

    frontier = compute_utility_frontier(empty, cfg)
    decision = build_decision_report(empty, cfg)

    assert frontier.empty
    assert set(frontier.columns) == {
        "method",
        "family",
        "lattice_type",
        "approximation_ratio",
        "valid_ratio",
        "runtime_seconds",
        "total_shots",
        "utility_score",
        "pareto_efficient",
        "decision_class",
        "dominates_any",
    }
    assert decision["recommendation"]["recommendation"] == "insufficient_data"
    assert decision["utility_frontier"] == []
    assert decision["lattice_type_rollup"] == []
    assert decision["quantum_favorable_windows"] == []
    assert decision["classical_favorable_windows"] == []
