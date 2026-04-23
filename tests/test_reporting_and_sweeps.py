from pathlib import Path

import pandas as pd

from hybrid_qaoa_portfolio.config import RunDeck
from hybrid_qaoa_portfolio.pipeline import run_benchmark_study


def test_validate_rejects_invalid_study_budget_ratio() -> None:
    cfg = RunDeck(study_budget_ratio=1.5)
    try:
        cfg.validate()
    except ValueError as exc:
        assert "study_budget_ratio" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid study_budget_ratio")


def test_benchmark_study_emits_findings_and_spin_sweep(tmp_path: Path) -> None:
    cfg = RunDeck(
        runtime_mode="local_proxy",
        n_assets=4,
        budget=2,
        depth=1,
        fourier_modes=1,
        bo_iters=2,
        sobol_init_iters=1,
        spsa_iters=2,
        random_search_iters=2,
        classical_bo_iters=2,
        base_shots=16,
        use_zne=False,
        use_readout_mitigation=False,
        study_num_seeds=1,
        study_regimes=("clustered",),
        study_n_assets=(4, 6),
        study_budget_ratio=0.5,
        study_depths=(1,),
        study_shot_budgets=(16,),
        study_noise_levels=(0.0,),
        output_prefix=str(tmp_path / "runtime_qaoa_test"),
    )
    result = run_benchmark_study(cfg)
    findings_md = Path(result["findings_md_path"])
    findings_json = Path(result["findings_json_path"])
    aggregates = pd.read_csv(result["aggregates_path"])

    assert findings_md.exists()
    assert findings_json.exists()
    assert "Explicit answers" in findings_md.read_text()
    assert set(aggregates["n_spins"].unique()) == {4, 6}
