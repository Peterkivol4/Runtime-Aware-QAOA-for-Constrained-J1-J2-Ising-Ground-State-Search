from __future__ import annotations

import hashlib
import json
import math
import platform
import sqlite3
from dataclasses import asdict
from datetime import date, datetime, time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .optional_deps import load_pandas

from ionmesh_runtime.interfaces import ResultLedger
from .config import RunDeck, TrialResult
from .constants import DEFAULT_BOOTSTRAP, DEFAULT_RUNTIME_MESSAGES, DEFAULT_SQLITE


SCHEMA_VERSION = 4


def physics_label_payload(payload: dict[str, Any]) -> dict[str, Any]:
    labeled = dict(payload)
    if "regime" in labeled and "lattice_type" not in labeled:
        labeled["lattice_type"] = labeled.pop("regime")
    else:
        labeled.pop("regime", None)
    if "valid_ratio" in labeled and "valid_sector_ratio" not in labeled:
        labeled["valid_sector_ratio"] = labeled["valid_ratio"]
    return labeled


def sanitize_json_payload(payload: Any) -> Any:
    pd = load_pandas()
    if payload is None or isinstance(payload, (str, int, bool)):
        return payload
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, dict):
        return {str(key): sanitize_json_payload(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple, set)):
        return [sanitize_json_payload(value) for value in payload]
    if isinstance(payload, pd.DataFrame):
        return [sanitize_json_payload(row) for row in payload.to_dict(orient="records")]
    if isinstance(payload, (pd.Series, pd.Index)):
        return [sanitize_json_payload(value) for value in payload.tolist()]
    if isinstance(payload, np.ndarray):
        return [sanitize_json_payload(value) for value in payload.tolist()]
    if isinstance(payload, pd.Timestamp):
        return payload.isoformat()
    if isinstance(payload, pd.Timedelta):
        return payload.isoformat() if hasattr(payload, "isoformat") else str(payload)
    if isinstance(payload, (datetime, date, time)):
        return payload.isoformat()
    if isinstance(payload, np.floating):
        payload = float(payload)
    if isinstance(payload, float):
        return payload if math.isfinite(payload) else None
    if isinstance(payload, np.integer):
        return int(payload)
    if isinstance(payload, np.bool_):
        return bool(payload)
    if hasattr(payload, "item"):
        try:
            return sanitize_json_payload(payload.item())
        except Exception:
            pass
    if hasattr(payload, "tolist") and not isinstance(payload, (str, bytes, bytearray)):
        try:
            return sanitize_json_payload(payload.tolist())
        except Exception:
            pass
    return payload


def json_dumps_clean(payload: Any, **kwargs: Any) -> str:
    return json.dumps(sanitize_json_payload(payload), allow_nan=False, **kwargs)



def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def environment_snapshot() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            "numpy": _package_version("numpy"),
            "scipy": _package_version("scipy"),
            "pandas": _package_version("pandas"),
            "matplotlib": _package_version("matplotlib"),
            "qiskit": _package_version("qiskit"),
            "qiskit-aer": _package_version("qiskit-aer"),
            "qiskit-ibm-runtime": _package_version("qiskit-ibm-runtime"),
            "mlflow": _package_version("mlflow"),
        },
    }


class RunLedger(ResultLedger):
    def __init__(self, name: str, *, tracker_backend: str = "sqlite", tracker_uri: str | None = None):
        self.name = name
        self.tracker_backend = tracker_backend
        self.tracker_uri = tracker_uri
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.payload: dict[str, Any] = {
            "metadata": {"name": name, "timestamp": self.timestamp, "environment": environment_snapshot()},
            "config": {},
            "records": [],
            "summary": {},
        }

    def log_config(self, cfg: RunDeck) -> None:
        self.payload["config"] = asdict(cfg)

    def log_records(self, records: list[TrialResult]) -> None:
        self.payload["records"] = [physics_label_payload(record.as_dict()) for record in records]

    def log_summary(self, summary: dict[str, Any]) -> None:
        self.payload["summary"] = summary

    def save_json(self, output_prefix: str) -> Path:
        path = Path(f"{output_prefix}_{self.timestamp}_results.json")
        path.write_text(json_dumps_clean(self.payload, indent=2))
        return path

    def save_csv(self, output_prefix: str) -> Path:
        path = Path(f"{output_prefix}_{self.timestamp}_summary.csv")
        pd = load_pandas()
        pd.DataFrame(self.payload.get("records", [])).drop(columns=["trace"], errors="ignore").to_csv(path, index=False)
        return path

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(path, timeout=DEFAULT_SQLITE['timeout_seconds'])
        conn.execute(f"PRAGMA journal_mode={DEFAULT_SQLITE['journal_mode']};")
        conn.execute(f"PRAGMA synchronous={DEFAULT_SQLITE['synchronous']};")
        conn.execute(f"PRAGMA busy_timeout={DEFAULT_SQLITE['busy_timeout_ms']};")
        return conn

    @staticmethod
    def _ensure_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        existing = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        if existing is None:
            conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        elif int(existing[0]) != SCHEMA_VERSION:
            raise RuntimeError(DEFAULT_RUNTIME_MESSAGES['tracker_schema_mismatch'])

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_name TEXT,
                timestamp TEXT,
                config_json TEXT,
                summary_json TEXT,
                environment_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT,
                family TEXT,
                lattice_type TEXT,
                seed INTEGER,
                n_spins INTEGER,
                budget INTEGER,
                depth INTEGER,
                noise_level REAL,
                shot_budget INTEGER,
                parameterization TEXT,
                mitigation_label TEXT,
                constraint_handling TEXT,
                best_energy REAL,
                exact_energy REAL,
                approximation_gap REAL,
                approximation_ratio REAL,
                success INTEGER,
                valid_ratio REAL,
                measurement_success_probability REAL,
                runtime_seconds REAL,
                evaluations INTEGER,
                objective_calls INTEGER,
                sampler_calls INTEGER,
                primitive_calls INTEGER,
                total_shots INTEGER,
                final_readout_shots INTEGER,
                optimization_best_energy REAL,
                final_readout_energy REAL,
                final_readout_valid_ratio REAL,
                final_readout_raw_best REAL,
                final_bitstring TEXT,
                best_params_json TEXT,
                transpilation_metadata_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trace (
                record_id INTEGER,
                evaluation REAL,
                objective REAL,
                best_energy REAL,
                approximation_gap REAL,
                valid_ratio REAL,
                shots_used REAL,
                penalty_linear REAL,
                penalty_quadratic REAL,
                penalty_epoch REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS optimizer_checkpoints (
                run_key TEXT PRIMARY KEY,
                method TEXT,
                payload_json TEXT,
                updated_at TEXT
            )
            """
        )

    @staticmethod
    def initialize_sqlite(path: str | Path) -> Path:
        sqlite_path = Path(path)
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with RunLedger._connect(sqlite_path) as conn:
            RunLedger._ensure_schema(conn)
        return sqlite_path

    @staticmethod
    def make_run_key(cfg: RunDeck, method: str) -> str:
        payload = {
            "seed": cfg.seed,
            "lattice_type": cfg.lattice_type,
            "n_spins": cfg.n_spins,
            "budget": cfg.budget,
            "depth": cfg.depth,
            "noise_level": cfg.noise_level,
            "shot_budget": cfg.base_shots,
            "parameterization": cfg.parameterization,
            "constraint_handling": cfg.constraint_handling,
            "mitigation": {"readout": cfg.use_readout_mitigation, "zne": cfg.use_zne},
            "method": method,
            "run_label": cfg.runtime_run_label,
        }
        digest = hashlib.sha256(json_dumps_clean(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return digest[:24]

    @staticmethod
    def save_optimizer_checkpoint(path: str | Path, run_key: str, method: str, payload: dict[str, Any]) -> None:
        sqlite_path = RunLedger.initialize_sqlite(path)
        with RunLedger._connect(sqlite_path) as conn:
            conn.execute(
                """
                INSERT INTO optimizer_checkpoints (run_key, method, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_key) DO UPDATE SET
                    method=excluded.method,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (run_key, method, json_dumps_clean(payload), datetime.now().isoformat()),
            )

    @staticmethod
    def load_optimizer_checkpoint(path: str | Path, run_key: str) -> dict[str, Any] | None:
        sqlite_path = Path(path)
        if not sqlite_path.exists():
            return None
        with RunLedger._connect(sqlite_path) as conn:
            row = conn.execute("SELECT payload_json FROM optimizer_checkpoints WHERE run_key = ?", (run_key,)).fetchone()
        return None if row is None else json.loads(row[0])

    @staticmethod
    def clear_optimizer_checkpoint(path: str | Path, run_key: str) -> None:
        sqlite_path = Path(path)
        if not sqlite_path.exists():
            return
        with RunLedger._connect(sqlite_path) as conn:
            conn.execute("DELETE FROM optimizer_checkpoints WHERE run_key = ?", (run_key,))

    @staticmethod
    def merge_sqlite_runs(output_path: str | Path, input_paths: Iterable[str | Path]) -> Path:
        output = Path(output_path)
        if output.exists():
            output.unlink()
        RunLedger.initialize_sqlite(output)
        with RunLedger._connect(output) as dst:
            for src_path in input_paths:
                with sqlite3.connect(Path(src_path)) as src:
                    for row in src.execute("SELECT run_name, timestamp, config_json, summary_json, environment_json FROM runs"):
                        dst.execute("INSERT INTO runs (run_name, timestamp, config_json, summary_json, environment_json) VALUES (?, ?, ?, ?, ?)", row)
                    for row in src.execute(
                        "SELECT record_id, method, family, lattice_type, seed, n_spins, budget, depth, noise_level, shot_budget, parameterization, mitigation_label, constraint_handling, best_energy, exact_energy, approximation_gap, approximation_ratio, success, valid_ratio, measurement_success_probability, runtime_seconds, evaluations, objective_calls, sampler_calls, primitive_calls, total_shots, final_readout_shots, optimization_best_energy, final_readout_energy, final_readout_valid_ratio, final_readout_raw_best, final_bitstring, best_params_json, transpilation_metadata_json FROM records"
                    ):
                        original_id = row[0]
                        cursor = dst.execute(
                            """
                            INSERT INTO records (
                                method, family, lattice_type, seed, n_spins, budget, depth, noise_level, shot_budget,
                                parameterization, mitigation_label, constraint_handling,
                                best_energy, exact_energy, approximation_gap, approximation_ratio, success,
                                valid_ratio, measurement_success_probability, runtime_seconds, evaluations, objective_calls,
                                sampler_calls, primitive_calls, total_shots, final_readout_shots,
                                optimization_best_energy, final_readout_energy, final_readout_valid_ratio, final_readout_raw_best,
                                final_bitstring, best_params_json, transpilation_metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            row[1:],
                        )
                        new_record_id = int(cursor.lastrowid)
                        for trace_row in src.execute(
                            "SELECT evaluation, objective, best_energy, approximation_gap, valid_ratio, shots_used, penalty_linear, penalty_quadratic, penalty_epoch FROM trace WHERE record_id = ?",
                            (original_id,),
                        ):
                            dst.execute(
                                "INSERT INTO trace (record_id, evaluation, objective, best_energy, approximation_gap, valid_ratio, shots_used, penalty_linear, penalty_quadratic, penalty_epoch) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (new_record_id, *trace_row),
                            )
        return output

    def save_sqlite(self, output_prefix: str, existing_path: str | Path | None = None) -> Path:
        path = Path(existing_path) if existing_path is not None else Path(f"{output_prefix}_{self.timestamp}.sqlite")
        self.initialize_sqlite(path)
        records = self.payload.get("records", [])
        with self._connect(path) as conn:
            conn.execute(
                "INSERT INTO runs (run_name, timestamp, config_json, summary_json, environment_json) VALUES (?, ?, ?, ?, ?)",
                (
                    self.name,
                    self.timestamp,
                    json_dumps_clean(self.payload.get("config", {})),
                    json_dumps_clean(self.payload.get("summary", {})),
                    json_dumps_clean(self.payload.get("metadata", {}).get("environment", {})),
                ),
            )
            for record in records:
                cursor = conn.execute(
                    """
                    INSERT INTO records (
                        method, family, lattice_type, seed, n_spins, budget, depth, noise_level, shot_budget,
                        parameterization, mitigation_label, constraint_handling,
                        best_energy, exact_energy, approximation_gap, approximation_ratio, success,
                        valid_ratio, measurement_success_probability, runtime_seconds, evaluations, objective_calls,
                        sampler_calls, primitive_calls, total_shots, final_readout_shots,
                        optimization_best_energy, final_readout_energy, final_readout_valid_ratio, final_readout_raw_best,
                        final_bitstring, best_params_json, transpilation_metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.get("method"),
                        record.get("family"),
                        record.get("lattice_type", record.get("regime")),
                        record.get("seed"),
                        record.get("n_spins"),
                        record.get("budget"),
                        record.get("depth"),
                        record.get("noise_level"),
                        record.get("shot_budget"), record.get("parameterization"), record.get("mitigation_label"),
                        record.get("constraint_handling"), record.get("best_energy"), record.get("exact_energy"),
                        record.get("approximation_gap"), record.get("approximation_ratio"), int(bool(record.get("success"))),
                        record.get("valid_ratio"), record.get("measurement_success_probability"), record.get("runtime_seconds"),
                        record.get("evaluations"), record.get("objective_calls"), record.get("sampler_calls", 0),
                        record.get("primitive_calls", record.get("objective_calls")), record.get("total_shots"),
                        record.get("final_readout_shots", 0), record.get("optimization_best_energy"),
                        record.get("final_readout_energy"), record.get("final_readout_valid_ratio"),
                        record.get("final_readout_raw_best"), record.get("final_bitstring"),
                        json_dumps_clean(record.get("best_params", [])),
                        json_dumps_clean(record.get("transpilation_metadata", {})),
                    ),
                )
                record_id = int(cursor.lastrowid)
                for step in record.get("trace", []):
                    conn.execute(
                        """
                        INSERT INTO trace (
                            record_id, evaluation, objective, best_energy, approximation_gap,
                            valid_ratio, shots_used, penalty_linear, penalty_quadratic, penalty_epoch
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record_id, step.get("evaluation"), step.get("objective"), step.get("best_energy"),
                            step.get("approximation_gap"), step.get("valid_ratio"), step.get("shots_used"),
                            step.get("penalty_linear", 0.0), step.get("penalty_quadratic", 0.0), step.get("penalty_epoch", 0.0),
                        ),
                    )
        self._maybe_log_mlflow(path)
        return path

    def _maybe_log_mlflow(self, sqlite_path: Path) -> None:
        if self.tracker_backend not in {"mlflow", "both"}:
            return
        if mlflow is None:
            return
        if self.tracker_uri:
            mlflow.set_tracking_uri(self.tracker_uri)
        mlflow.set_experiment(self.name)
        with mlflow.start_run(run_name=f"{self.name}_{self.timestamp}"):
            mlflow.log_params(self.payload.get("config", {}))
            summary = self.payload.get("summary", {})
            for key, value in summary.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(key, value)
            mlflow.log_dict(self.payload.get("metadata", {}).get("environment", {}), "environment.json")
            mlflow.log_artifact(str(sqlite_path))
            temp_json = self.save_json(str(sqlite_path.with_suffix("")))
            mlflow.log_artifact(str(temp_json))

__all__ = [
    'SCHEMA_VERSION',
    'sanitize_json_payload',
    'json_dumps_clean',
    'environment_snapshot',
    'physics_label_payload',
    'RunLedger',
]
