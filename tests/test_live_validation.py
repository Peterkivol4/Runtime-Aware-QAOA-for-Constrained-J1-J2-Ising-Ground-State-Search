from __future__ import annotations

from pathlib import Path

from ionmesh_runtime._internal import live_validation as live_validation_impl
from hybrid_qaoa_portfolio.config import RunDeck
from hybrid_qaoa_portfolio.live_certification import CertificationResult
from hybrid_qaoa_portfolio.live_validation import save_live_validation_report


def test_run_live_validation_suite_builds_repeatability_and_appendix_payload(monkeypatch) -> None:
    class DummyBackend:
        pass

    def fake_run_live_certification_check(cfg: RunDeck, *, backend_name: str | None = None) -> CertificationResult:
        return CertificationResult(
            passed=True,
            checks={
                "backend_name": backend_name or "ibm_fez",
                "selected_execution_mode": cfg.runtime_execution_mode,
            },
            notes=["ok"],
        )

    def fake_create_service(cfg: RunDeck, *, strict: bool | None = None) -> object:
        return object()

    def fake_select_backend(service: object, backend_name: str | None = None) -> DummyBackend:
        return DummyBackend()

    def fake_snapshot_payload(backend: DummyBackend) -> dict[str, object]:
        return {
            "backend_name": "ibm_fez",
            "num_qubits": 156,
            "basis_gates": ["rz", "sx", "ecr"],
            "qubits": [{"t1": 100.0, "t2": 120.0, "readout_error": 0.02}],
            "instruction_errors": {"ecr": [0.01]},
        }

    def fake_noise_profile_from_snapshot(snapshot: dict[str, object]) -> dict[str, float]:
        return {
            "t1_time": 100.0,
            "t2_time": 120.0,
            "readout_p10": 0.02,
            "readout_p01": 0.02,
            "depol_error": 0.01,
        }

    def fake_run_smoke_test(cfg: RunDeck) -> dict[str, object]:
        energy_shift = 0.05 if cfg.runtime_mode == "runtime_v2" else 0.02
        return {
            "best_energy": -1.0 + energy_shift + 0.001 * cfg.seed,
            "exact_energy": -1.2,
            "valid_ratio": 0.55 if cfg.runtime_mode == "runtime_v2" else 0.6,
            "success": False,
            "measurement_success_probability": 0.1 if cfg.runtime_mode == "runtime_v2" else 0.2,
            "final_bitstring": "1010",
            "runtime_seconds": 2.0 if cfg.runtime_mode == "runtime_v2" else 0.5,
            "total_shots": cfg.base_shots,
            "final_readout_shots": cfg.base_shots,
            "objective_calls": 3,
            "sampler_calls": 1,
            "transpilation_metadata": {
                "backend_name": cfg.runtime_backend if cfg.runtime_mode == "runtime_v2" else "aer",
                "session_plan": {
                    "requested_mode": cfg.runtime_execution_mode,
                    "selected_mode": "backend" if cfg.runtime_mode == "runtime_v2" else "backend",
                },
            },
        }

    monkeypatch.setattr(live_validation_impl, "run_live_certification_check", fake_run_live_certification_check)
    monkeypatch.setattr(live_validation_impl.RuntimeSamplerFactory, "create_service", staticmethod(fake_create_service))
    monkeypatch.setattr(live_validation_impl.RuntimeSamplerFactory, "select_backend", staticmethod(fake_select_backend))
    monkeypatch.setattr(live_validation_impl.RuntimeSamplerFactory, "calibration_snapshot_payload", staticmethod(fake_snapshot_payload))
    monkeypatch.setattr(live_validation_impl.RuntimeSamplerFactory, "noise_profile_from_snapshot", staticmethod(fake_noise_profile_from_snapshot))
    monkeypatch.setattr(live_validation_impl, "run_smoke_test", fake_run_smoke_test)

    cfg = RunDeck(runtime_mode="runtime_v2", runtime_backend="ibm_fez", runtime_execution_mode="session", seed=11)
    result = live_validation_impl.run_live_validation_suite(
        cfg,
        live_repeats=2,
        aer_repeats=2,
        appendix_n_spins=(4,),
        appendix_shot_budgets=(32,),
        appendix_seeds=1,
    )

    assert result["preflight"]["passed"] is True
    assert result["calibration_snapshot"]["backend_name"] == "ibm_fez"
    assert result["aer_noise_profile"]["depol_error"] == 0.01
    assert result["repeatability"]["hardware_summary"]["count"] == 2
    assert result["repeatability"]["aer_summary"]["count"] == 2
    assert result["repeatability"]["parity_summary"]["pair_count"] == 2
    assert result["appendix_sweep"]["summary"]["cell_count"] == 1


def test_save_live_validation_report_writes_snapshot(tmp_path: Path) -> None:
    result = {
        "observed_at": "2026-04-13T23:10:00+08:00",
        "preflight": {
            "passed": True,
            "checks": {
                "backend_name": "ibm_fez",
                "selected_execution_mode": "backend",
            },
        },
        "calibration_snapshot": {"backend_name": "ibm_fez", "num_qubits": 156},
        "repeatability": {
            "hardware_summary": {
                "count": 3,
                "best_energy": {"mean": -0.2, "stdev": 0.01},
                "valid_ratio": {"mean": 0.56},
            },
            "parity_summary": {
                "pair_count": 3,
                "delta_best_energy_hardware_minus_aer": {"mean": -0.03},
                "delta_valid_ratio_hardware_minus_aer": {"mean": -0.05},
            },
        },
        "appendix_sweep": {
            "summary": {
                "cell_count": 8,
                "hardware_valid_ratio_below_half_fraction": 0.25,
                "aer_valid_ratio_below_half_fraction": 0.0,
            }
        },
    }
    json_path, md_path, snapshot_path = save_live_validation_report(result, tmp_path / "live_suite")
    assert json_path.exists()
    assert md_path.exists()
    assert snapshot_path is not None and snapshot_path.exists()
    assert "ibm_fez" in md_path.read_text()
