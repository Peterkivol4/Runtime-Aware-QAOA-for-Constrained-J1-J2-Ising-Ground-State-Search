import sqlite3
from pathlib import Path

from hybrid_qaoa_portfolio.config import RunDeck
from hybrid_qaoa_portfolio.pipeline import PenaltyController, run_benchmark_study


def test_augmented_lagrangian_penalty_grows_when_valid_ratio_collapses() -> None:
    cfg = RunDeck(constraint_handling="penalty", penalty_schedule="augmented_lagrangian", penalty_strength=2.0)
    controller = PenaltyController.create(cfg, total_steps=10)
    before = controller.state(1)

    class Batch:
        valid_ratio = 0.2

    controller.observe(Batch())
    after = controller.state(2)
    assert after.quadratic_strength >= before.quadratic_strength
    assert after.linear_strength >= before.linear_strength


def test_benchmark_study_writes_sqlite_tracker(tmp_path: Path) -> None:
    prefix = tmp_path / "study"
    cfg = RunDeck(
        n_assets=5,
        budget=2,
        depth=1,
        fourier_modes=1,
        bo_iters=2,
        sobol_init_iters=2,
        random_search_iters=2,
        spsa_iters=2,
        classical_bo_iters=2,
        sa_steps=8,
        base_shots=8,
        study_num_seeds=1,
        study_regimes=("random",),
        study_depths=(1,),
        study_shot_budgets=(8,),
        study_noise_levels=(0.0,),
        output_prefix=str(prefix),
    )
    result = run_benchmark_study(cfg)
    sqlite_path = Path(result["sqlite_path"])
    assert sqlite_path.exists()
    with sqlite3.connect(sqlite_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"runs", "records", "trace"}.issubset(tables)
        record_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        assert record_count > 0


from hybrid_qaoa_portfolio.tracking import RunLedger


def test_sqlite_tracker_enables_wal_mode(tmp_path: Path) -> None:
    ledger = RunLedger("test")
    ledger.log_config(RunDeck())
    ledger.log_records([])
    ledger.log_summary({})
    sqlite_path = ledger.save_sqlite(str(tmp_path / "wal_test"))
    with sqlite3.connect(sqlite_path) as conn:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0].lower()
        assert mode == "wal"
