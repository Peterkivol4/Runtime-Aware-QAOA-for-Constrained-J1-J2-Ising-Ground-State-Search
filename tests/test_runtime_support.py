import pytest

from spinmesh_runtime.config import RunDeck
from spinmesh_runtime.runtime_support import RuntimeSamplerFactory, RuntimeSessionManager


@pytest.mark.skipif(RuntimeSamplerFactory.__dict__.get('build_generic_heavy_hex_backend') is None, reason='runtime support unavailable')
def test_generic_backend_isa_pass_manager_routes_circuit() -> None:
    qiskit = pytest.importorskip("qiskit")
    backend = RuntimeSamplerFactory.build_generic_heavy_hex_backend(num_qubits=7)
    circuit = qiskit.QuantumCircuit(7)
    circuit.h(0)
    circuit.cx(0, 6)
    circuit.measure_all()
    isa = RuntimeSamplerFactory.make_isa_circuit(circuit, backend)
    metadata = RuntimeSamplerFactory.transpilation_metadata(backend, isa)
    assert isa.num_qubits == 7
    assert metadata["basis_violations"] == []
    assert "cx" in metadata["executable_operations"]
    assert metadata["two_qubit_gate_count"] >= 1
    assert "swap_count" in metadata


def test_runtime_session_manager_falls_back_to_backend_on_open_plan_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeJob:
        def __init__(self, mode: str):
            self.mode = mode

        def job_id(self) -> str:
            return f"{self.mode}-job"

        def result(self) -> list[str]:
            if self.mode == "session":
                raise RuntimeError("Open plan is not authorized to run a session. Use a different execution mode. Code 1352.")
            return ["ok"]

    class FakePrimitive:
        def __init__(self, mode: str):
            self.mode = mode

        def run(self, pubs: list[object]) -> FakeJob:
            return FakeJob(self.mode)

    def fake_create_primitives(
        backend: object,
        *,
        execution_mode: str = "backend",
        use_twirling: bool = False,
        use_dynamical_decoupling: bool = False,
        resilience_level: int = 0,
    ) -> tuple[FakePrimitive, FakePrimitive, object | None]:
        return FakePrimitive(execution_mode), FakePrimitive(execution_mode), object() if execution_mode == "session" else None

    monkeypatch.setattr(RuntimeSamplerFactory, "create_primitives", staticmethod(fake_create_primitives))

    cfg = RunDeck(runtime_execution_mode="session", runtime_retry_attempts=2, runtime_retry_backoff_seconds=0.0)
    manager = RuntimeSessionManager(cfg, backend=object())

    assert manager.run_estimator([("pub",)]) == ["ok"]
    metadata = manager.metadata()
    assert metadata["selected_mode"] == "backend"
    assert metadata["mode_history"] == ["session", "backend"]
    assert metadata["fallback_count"] == 1
    assert metadata["recovery_events"][0]["from_mode"] == "session"
    assert metadata["job_log"][0]["status"] == "failed"
    assert metadata["job_log"][1]["status"] == "completed"


def test_runtime_session_manager_falls_back_when_session_open_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePrimitive:
        def __init__(self, mode: str):
            self.mode = mode

        def run(self, pubs: list[object]) -> object:
            class FakeJob:
                @staticmethod
                def job_id() -> str:
                    return "backend-job"

                @staticmethod
                def result() -> list[str]:
                    return ["ok"]

            return FakeJob()

    def fake_create_primitives(
        backend: object,
        *,
        execution_mode: str = "backend",
        use_twirling: bool = False,
        use_dynamical_decoupling: bool = False,
        resilience_level: int = 0,
    ) -> tuple[FakePrimitive, FakePrimitive, object | None]:
        if execution_mode == "session":
            raise RuntimeError("You are not authorized to run a session when using the open plan. Code 1352.")
        return FakePrimitive(execution_mode), FakePrimitive(execution_mode), None

    monkeypatch.setattr(RuntimeSamplerFactory, "create_primitives", staticmethod(fake_create_primitives))

    cfg = RunDeck(runtime_execution_mode="session", runtime_retry_attempts=2, runtime_retry_backoff_seconds=0.0)
    manager = RuntimeSessionManager(cfg, backend=object())
    metadata = manager.metadata()
    assert metadata["selected_mode"] == "backend"
    assert metadata["mode_history"] == ["session", "backend"]
    assert metadata["fallback_count"] == 1
    assert metadata["recovery_events"][0]["to_mode"] == "backend"


def test_calibration_snapshot_payload_supports_qubit_properties_list() -> None:
    class DummyProps:
        def __init__(self, t1: float, t2: float, readout_error: float):
            self.t1 = t1
            self.t2 = t2
            self.readout_error = readout_error

    class DummyInstruction:
        properties = type("P", (), {"error": 0.02})()

    class DummyTarget:
        num_qubits = 2
        operation_names = ["rz", "cx"]
        qubit_properties = [DummyProps(100.0, 120.0, 0.01), DummyProps(110.0, 130.0, 0.02)]
        instructions = [(type("Op", (), {"name": "cx"})(), (0, 1))]

        def __getitem__(self, name: str) -> dict[tuple[int, int], DummyInstruction]:
            return {(0, 1): DummyInstruction()}

    class DummyCouplingMap:
        @staticmethod
        def get_edges() -> list[tuple[int, int]]:
            return [(0, 1)]

    class DummyBackend:
        target = DummyTarget()
        coupling_map = DummyCouplingMap()
        name = "dummy_backend"

    payload = RuntimeSamplerFactory.calibration_snapshot_payload(DummyBackend())
    assert payload["backend_name"] == "dummy_backend"
    assert payload["qubits"][0]["t1"] == 100.0
    assert payload["instruction_errors"]["cx"] == [0.02]


def test_calibration_snapshot_payload_skips_non_string_instruction_names() -> None:
    class DummyTarget:
        num_qubits = 1
        operation_names = ["rz"]
        qubit_properties = []
        instructions = [(type("OpClass", (), {"name": property(lambda self: "rz")}), (0,))]

        def __getitem__(self, name: str) -> dict[tuple[int], object]:
            raise AssertionError("Non-string operation names should be skipped before lookup.")

    class DummyBackend:
        target = DummyTarget()
        coupling_map = None
        name = "dummy_backend"

    payload = RuntimeSamplerFactory.calibration_snapshot_payload(DummyBackend())
    assert payload["instruction_errors"] == {}
