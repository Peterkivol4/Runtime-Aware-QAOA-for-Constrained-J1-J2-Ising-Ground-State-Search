from hybrid_qaoa_portfolio.config import RunDeck
from hybrid_qaoa_portfolio.pipeline import run_single_benchmark, run_smoke_test


def test_smoke_test_runs_without_quantum_stack() -> None:
    result = run_smoke_test(RunDeck(depth=1, fourier_modes=1, bo_iters=3, sobol_init_iters=2, random_search_iters=3, spsa_iters=3, base_shots=16))
    assert 0.0 <= result["valid_ratio"] <= 1.0
    assert result["lattice_type"] == "j1j2_frustrated"
    assert "j2_ratio" in result
    assert "approximation_gap" in result


def test_single_benchmark_returns_records() -> None:
    cfg = RunDeck(
        n_assets=5,
        budget=2,
        depth=2,
        fourier_modes=1,
        bo_iters=4,
        sobol_init_iters=2,
        random_search_iters=4,
        spsa_iters=4,
        classical_bo_iters=4,
        base_shots=16,
    )
    result = run_single_benchmark(cfg)
    assert len(result["records"]) >= 6
    qaoa_records = [record for record in result["records"] if record["family"] == "qaoa"]
    assert all("lattice_type" in record for record in result["records"])
    assert all("n_spins" in record for record in result["records"])
    assert all(record["final_bitstring"] for record in qaoa_records)
    assert all(record["objective_calls"] > 0 for record in qaoa_records)
    assert all(record["optimization_best_energy"] is not None for record in qaoa_records)
    assert all(record["final_readout_energy"] is not None for record in qaoa_records)


def test_spsa_accounting_counts_hidden_perturbation_calls() -> None:
    cfg = RunDeck(
        n_spins=4,
        magnetization_m=0,
        depth=1,
        fourier_modes=1,
        bo_iters=1,
        sobol_init_iters=1,
        random_search_iters=1,
        spsa_iters=2,
        classical_bo_iters=1,
        base_shots=8,
        use_zne=False,
        use_readout_mitigation=False,
        dynamic_shots_enabled=False,
        shot_governor_enabled=False,
        runtime_mode="local_proxy",
    )
    result = run_single_benchmark(cfg)
    spsa_record = next(record for record in result["records"] if record["method"] == "spsa_fourier")

    assert spsa_record["evaluations"] == 2
    assert spsa_record["objective_calls"] == 6
    assert spsa_record["total_shots"] == 56
