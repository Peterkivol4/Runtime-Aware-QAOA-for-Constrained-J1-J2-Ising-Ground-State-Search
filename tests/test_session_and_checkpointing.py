import sqlite3
from pathlib import Path

from hybrid_qaoa_portfolio.config import RunDeck
from hybrid_qaoa_portfolio.runtime_support import RuntimeExecutionPlan
from hybrid_qaoa_portfolio.tracking import RunLedger, SCHEMA_VERSION


def test_sqlite_schema_version_is_initialized(tmp_path: Path) -> None:
    sqlite_path = RunLedger.initialize_sqlite(tmp_path / "schema.sqlite")
    with sqlite3.connect(sqlite_path) as conn:
        version = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    assert int(version) == SCHEMA_VERSION


def test_optimizer_checkpoint_roundtrip(tmp_path: Path) -> None:
    sqlite_path = RunLedger.initialize_sqlite(tmp_path / "ckpt.sqlite")
    cfg = RunDeck(seed=7, n_assets=4, budget=2, depth=1, fourier_modes=1)
    run_key = RunLedger.make_run_key(cfg, "bo_fourier")
    payload = {"evaluation": 3, "best_energy": -1.23, "trace": [{"evaluation": 1}]}
    RunLedger.save_optimizer_checkpoint(sqlite_path, run_key, "bo_fourier", payload)
    restored = RunLedger.load_optimizer_checkpoint(sqlite_path, run_key)
    assert restored is not None
    assert restored["evaluation"] == 3
    RunLedger.clear_optimizer_checkpoint(sqlite_path, run_key)
    assert RunLedger.load_optimizer_checkpoint(sqlite_path, run_key) is None


def test_runtime_execution_plan_payload() -> None:
    plan = RuntimeExecutionPlan(
        requested_mode="auto",
        selected_mode="batch",
        estimated_total_shots=64000,
        retry_attempts=3,
        uses_persistent_context=True,
    )
    payload = plan.as_dict()
    assert payload["selected_mode"] == "batch"
    assert payload["estimated_total_shots"] == 64000
