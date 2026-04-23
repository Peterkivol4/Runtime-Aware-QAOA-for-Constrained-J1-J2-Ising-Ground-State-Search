from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .tracking import json_dumps_clean
from statistics import mean
from typing import Any, Callable

from ionmesh_runtime.interfaces import RuntimeSession
from .config import RunDeck
from .constants import DEFAULT_GENERIC_BACKEND, DEFAULT_NOISE_PROFILE, DEFAULT_RUNTIME_MESSAGES
from .secrets import SecretsManager
from .optional_deps import load_qiskit_fake_backend, load_qiskit_runtime_v2


@dataclass
class RuntimeSupportStatus:
    available: bool
    message: str


@dataclass
class RuntimeExecutionPlan:
    requested_mode: str
    selected_mode: str
    estimated_total_shots: int
    retry_attempts: int
    uses_persistent_context: bool
    selection_reason: str = "explicit_request"
    mode_history: list[str] = field(default_factory=list)
    fallback_count: int = 0
    fallback_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested_mode": self.requested_mode,
            "selected_mode": self.selected_mode,
            "estimated_total_shots": int(self.estimated_total_shots),
            "retry_attempts": int(self.retry_attempts),
            "uses_persistent_context": bool(self.uses_persistent_context),
            "selection_reason": self.selection_reason,
            "mode_history": list(self.mode_history),
            "fallback_count": int(self.fallback_count),
            "fallback_reason": self.fallback_reason,
        }


def _fake_backend_tools() -> dict[str, Any] | None:
    try:
        return load_qiskit_fake_backend()
    except Exception:
        return None


def _runtime_v2_tools() -> dict[str, Any] | None:
    try:
        return load_qiskit_runtime_v2()
    except Exception:
        return None


def _runtime_error_types() -> tuple[type[Exception], ...]:
    tools = _runtime_v2_tools()
    if not tools:
        return (Exception,)
    return (
        tools["IBMRestRuntimeError"],
        tools["IBMRuntimeError"],
        tools["IBMRuntimeApiError"],
        tools["IBMRuntimeJobFailureError"],
    )


RECOVERABLE_RUNTIME_ERRORS = _runtime_error_types()


def runtime_status() -> RuntimeSupportStatus:
    tools = _runtime_v2_tools()
    if not tools:
        return RuntimeSupportStatus(
            available=False,
            message=DEFAULT_RUNTIME_MESSAGES['runtime_unavailable'],
        )
    return RuntimeSupportStatus(available=True, message="Runtime V2 support is available.")


class RuntimeSamplerFactory:
    NON_EXECUTABLE_OPS = frozenset({"barrier"})

    @staticmethod
    def create_service(cfg: RunDeck | None = None, *, strict: bool | None = None) -> Any:
        status = runtime_status()
        if not status.available:  # pragma: no cover - optional dependency
            raise ImportError(status.message)
        if strict is None:
            strict = bool(cfg and cfg.runtime_mode == 'runtime_v2')
        secret_box = SecretsManager.runtime(strict=bool(strict))
        kwargs = secret_box.service_kwargs()
        tools = _runtime_v2_tools()
        if tools is None:  # pragma: no cover - optional dependency
            raise ImportError(status.message)
        svc = tools["QiskitRuntimeService"]
        if kwargs:
            return svc(**kwargs)
        return svc()

    @staticmethod
    def select_backend(service: Any, backend_name: str | None = None) -> Any:
        if backend_name is not None:
            return service.backend(backend_name)
        return service.least_busy(operational=True, simulator=False)

    @staticmethod
    def make_isa_circuit(circuit: Any, backend: Any, *, optimization_level: int = 1) -> Any:
        tools = _fake_backend_tools()
        if tools is None:  # pragma: no cover - optional dependency
            raise ImportError("qiskit transpiler is unavailable.")
        pass_manager = tools["generate_preset_pass_manager"](backend=backend, optimization_level=optimization_level)
        return pass_manager.run(circuit)

    @staticmethod
    def calibration_snapshot_payload(backend: Any) -> dict[str, Any]:
        target = getattr(backend, "target", None)
        basis = list(getattr(target, "operation_names", []) or getattr(backend, "operation_names", []))
        target_num_qubits = getattr(target, "num_qubits", None)
        if target_num_qubits is None:
            num_qubits = int(getattr(backend, "num_qubits", 0))
        else:
            num_qubits = int(target_num_qubits)
        coupling_map = []
        cmap = getattr(backend, "coupling_map", None)
        if cmap is not None and hasattr(cmap, "get_edges"):
            coupling_map = [list(edge) for edge in cmap.get_edges()]
        elif cmap is not None:
            coupling_map = [list(edge) for edge in cmap]
        qubit_props = []
        qubit_properties = getattr(target, "qubit_properties", None) if target is not None else None
        if qubit_properties is not None:
            for index in range(num_qubits):
                if callable(qubit_properties):
                    props = qubit_properties(index)
                elif isinstance(qubit_properties, (list, tuple)):
                    props = qubit_properties[index] if index < len(qubit_properties) else None
                else:
                    props = None
                if props is None:
                    qubit_props.append({"t1": None, "t2": None, "readout_error": None})
                else:
                    qubit_props.append(
                        {
                            "t1": getattr(props, "t1", None),
                            "t2": getattr(props, "t2", None),
                            "readout_error": getattr(props, "readout_error", None),
                        }
                    )
        instruction_errors: dict[str, list[float]] = {}
        if target is not None and hasattr(target, "instructions"):
            for operation, qargs in target.instructions:
                op_name = getattr(operation, "name", str(operation))
                if not isinstance(op_name, str):
                    continue
                try:
                    instruction_map = target[op_name]
                except Exception:
                    continue
                get_entry = getattr(instruction_map, "get", None)
                instruction = get_entry(qargs) if callable(get_entry) else None
                if instruction is None:
                    continue
                props = getattr(instruction, "properties", None)
                error = getattr(props, "error", None)
                if error is not None:
                    instruction_errors.setdefault(op_name, []).append(float(error))
        backend_name = getattr(backend, "name", None)
        if callable(backend_name):
            backend_name = backend_name()
        return {
            "backend_name": backend_name or str(backend),
            "num_qubits": num_qubits,
            "basis_gates": basis,
            "coupling_map": coupling_map,
            "qubits": qubit_props,
            "instruction_errors": instruction_errors,
        }

    @staticmethod
    def save_calibration_snapshot(service: Any, backend_name: str, output_path: str | Path) -> Path:
        backend = RuntimeSamplerFactory.select_backend(service, backend_name)
        payload = RuntimeSamplerFactory.calibration_snapshot_payload(backend)
        path = Path(output_path)
        path.write_text(json_dumps_clean(payload, indent=2))
        return path

    @staticmethod
    def load_calibration_snapshot(snapshot_path: str | Path) -> dict[str, Any]:
        return json.loads(Path(snapshot_path).read_text())

    @staticmethod
    def noise_profile_from_snapshot(snapshot: dict[str, Any]) -> dict[str, float]:
        qubits = snapshot.get("qubits", [])
        instruction_errors = snapshot.get("instruction_errors", {})
        t1_values = [float(q["t1"]) for q in qubits if q.get("t1") is not None]
        t2_values = [float(q["t2"]) for q in qubits if q.get("t2") is not None]
        readouts = [float(q["readout_error"]) for q in qubits if q.get("readout_error") is not None]
        gate_errors = [float(v) for values in instruction_errors.values() for v in values if v is not None]
        return {
            "t1_time": float(mean(t1_values)) if t1_values else DEFAULT_NOISE_PROFILE['t1_time'],
            "t2_time": float(mean(t2_values)) if t2_values else DEFAULT_NOISE_PROFILE['t2_time'],
            "readout_p10": float(mean(readouts)) if readouts else DEFAULT_NOISE_PROFILE['readout_p10'],
            "readout_p01": float(mean(readouts)) if readouts else DEFAULT_NOISE_PROFILE['readout_p01'],
            "depol_error": float(mean(gate_errors)) if gate_errors else DEFAULT_NOISE_PROFILE['depol_error'],
        }

    @staticmethod
    def build_generic_heavy_hex_backend(
        num_qubits: int = 7,
        *,
        seed: int = 11,
        calibration_snapshot: dict[str, Any] | None = None,
    ) -> Any:
        tools = _fake_backend_tools()
        if tools is None:  # pragma: no cover - optional dependency
            raise ImportError("qiskit fake_provider is unavailable.")
        GenericBackendV2 = tools["GenericBackendV2"]
        snapshot = calibration_snapshot or {}
        coupling_map = snapshot.get("coupling_map") or DEFAULT_GENERIC_BACKEND['coupling_map']
        basis_gates = snapshot.get("basis_gates") or DEFAULT_GENERIC_BACKEND['basis_gates']
        backend = GenericBackendV2(
            num_qubits=int(snapshot.get("num_qubits", num_qubits or DEFAULT_GENERIC_BACKEND['num_qubits'])),
            coupling_map=coupling_map,
            basis_gates=basis_gates,
            seed=seed if seed is not None else DEFAULT_GENERIC_BACKEND['seed'],
        )
        setattr(backend, "offline_calibration_snapshot", snapshot)
        return backend

    @staticmethod
    def create_primitives(
        backend: Any,
        *,
        execution_mode: str = "backend",
        use_twirling: bool = False,
        use_dynamical_decoupling: bool = False,
        resilience_level: int = 0,
    ) -> tuple[Any, Any, Any | None]:
        status = runtime_status()
        if not status.available:  # pragma: no cover - optional dependency
            raise ImportError(status.message)

        context: Any | None = None
        primitive_mode: Any = backend
        tools = _runtime_v2_tools()
        if tools is None:  # pragma: no cover - optional dependency
            raise ImportError(status.message)
        if execution_mode == "session":
            context = tools["Session"](backend=backend)
            primitive_mode = context
        elif execution_mode == "batch":
            context = tools["Batch"](backend=backend)
            primitive_mode = context

        sampler = tools["SamplerV2"](mode=primitive_mode)
        estimator = tools["EstimatorV2"](mode=primitive_mode)
        estimator.options.resilience_level = resilience_level

        sampler.options.twirling.enable_gates = bool(use_twirling)
        sampler.options.twirling.enable_measure = bool(use_twirling)
        sampler.options.dynamical_decoupling.enable = bool(use_dynamical_decoupling)
        if use_dynamical_decoupling:
            sampler.options.dynamical_decoupling.sequence_type = "XpXm"
        return estimator, sampler, context

    @staticmethod
    def executable_instruction_names(circuit: Any) -> list[str]:
        names: list[str] = []
        for instruction in getattr(circuit, "data", []):
            operation = getattr(instruction, "operation", None)
            name = getattr(operation, "name", None)
            if name is None or name in RuntimeSamplerFactory.NON_EXECUTABLE_OPS:
                continue
            names.append(name)
        return names

    @staticmethod
    def isa_basis_violations(backend: Any, isa_circuit: Any) -> list[str]:
        basis = set(list(getattr(getattr(backend, "target", None), "operation_names", []) or getattr(backend, "operation_names", [])))
        return sorted({name for name in RuntimeSamplerFactory.executable_instruction_names(isa_circuit) if name not in basis})

    @staticmethod
    def transpilation_metadata(backend: Any, isa_circuit: Any, *, optimization_level: int = 1) -> dict[str, Any]:
        basis = list(getattr(getattr(backend, "target", None), "operation_names", []) or getattr(backend, "operation_names", []))
        backend_name = getattr(backend, "name", None)
        if callable(backend_name):
            backend_name = backend_name()
        payload = {
            "backend_name": backend_name or str(backend),
            "optimization_level": int(optimization_level),
            "num_qubits": int(getattr(isa_circuit, "num_qubits", 0)),
            "depth": int(isa_circuit.depth() if hasattr(isa_circuit, "depth") else 0),
            "size": int(isa_circuit.size() if hasattr(isa_circuit, "size") else 0),
            "basis_gates": basis,
            "executable_operations": RuntimeSamplerFactory.executable_instruction_names(isa_circuit),
            "basis_violations": RuntimeSamplerFactory.isa_basis_violations(backend, isa_circuit),
            "layout": str(getattr(isa_circuit, "layout", None)),
        }
        snapshot = getattr(backend, "offline_calibration_snapshot", None)
        if snapshot:
            payload["offline_calibration_snapshot"] = snapshot.get("backend_name", "snapshot")
        return payload


class RuntimeSessionManager(RuntimeSession):
    def __init__(self, cfg: RunDeck, backend: Any, *, open_context: bool = True):
        self.cfg = cfg
        self.backend = backend
        self.context: Any | None = None
        self.estimator: Any | None = None
        self.sampler: Any | None = None
        self.recovery_events: list[dict[str, Any]] = []
        self.job_log: list[dict[str, Any]] = []
        self.plan = self._select_plan()
        if open_context:
            self._open()

    def __enter__(self) -> "RuntimeSessionManager":
        self.ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _select_plan(self) -> RuntimeExecutionPlan:
        requested = self.cfg.runtime_execution_mode
        estimated = int(self.cfg.runtime_estimated_total_shots or 0)
        if requested == "auto":
            if estimated <= 0:
                selected = "backend"
                reason = "no_estimated_shot_budget"
            elif estimated >= self.cfg.runtime_auto_batch_shot_threshold:
                selected = "batch"
                reason = "estimated_shots_exceed_batch_threshold"
            else:
                selected = "session"
                reason = "iterative_workload_with_moderate_budget"
        else:
            selected = requested
            reason = "explicit_request"
        return RuntimeExecutionPlan(
            requested_mode=requested,
            selected_mode=selected,
            estimated_total_shots=estimated,
            retry_attempts=self.cfg.runtime_retry_attempts,
            uses_persistent_context=selected in {"session", "batch"},
            selection_reason=reason,
            mode_history=[selected],
        )

    def _open(self) -> None:
        try:
            self.estimator, self.sampler, self.context = RuntimeSamplerFactory.create_primitives(
                self.backend,
                execution_mode=self.plan.selected_mode,
                use_twirling=self.cfg.use_twirling,
                use_dynamical_decoupling=self.cfg.use_dynamical_decoupling,
                resilience_level=self.cfg.runtime_resilience_level,
            )
        except Exception as exc:
            if not self._fallback_to_backend(exc):
                raise
            self.estimator, self.sampler, self.context = RuntimeSamplerFactory.create_primitives(
                self.backend,
                execution_mode=self.plan.selected_mode,
                use_twirling=self.cfg.use_twirling,
                use_dynamical_decoupling=self.cfg.use_dynamical_decoupling,
                resilience_level=self.cfg.runtime_resilience_level,
            )

    def ensure_open(self) -> None:
        if self.estimator is None or self.sampler is None:
            self._open()

    def close(self) -> None:
        context = self.context
        self.context = None
        self.estimator = None
        self.sampler = None
        if context is None:
            return
        try:
            close = getattr(context, "close", None)
            if callable(close):
                close()
                return
            cancel = getattr(context, "cancel", None)
            if callable(cancel):
                cancel()
        except Exception:
            pass

    def refresh(self) -> None:
        self.close()
        self._open()

    @staticmethod
    def _is_recoverable(exc: Exception) -> bool:
        if isinstance(exc, RECOVERABLE_RUNTIME_ERRORS):
            return True
        text = str(exc).lower()
        return any(token in text for token in ("session", "timeout", "timed out", "connection", "internal error", "job failure"))

    @staticmethod
    def _is_execution_mode_rejection(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(
            token in text
            for token in (
                "not authorized to run a session",
                "use a different execution mode",
                "open plan",
                "code 1352",
                "execution mode",
            )
        )

    def _fallback_to_backend(self, exc: Exception) -> bool:
        if self.plan.selected_mode == "backend":
            return False
        if self.plan.selected_mode not in {"session", "batch"}:
            return False
        if not self._is_execution_mode_rejection(exc):
            return False
        previous_mode = self.plan.selected_mode
        self.plan.selected_mode = "backend"
        self.plan.uses_persistent_context = False
        self.plan.selection_reason = "runtime_mode_rejected_backend_fallback"
        self.plan.fallback_count += 1
        self.plan.fallback_reason = str(exc)
        if not self.plan.mode_history or self.plan.mode_history[-1] != "backend":
            self.plan.mode_history.append("backend")
        self.recovery_events.append(
            {
                "event": "execution_mode_fallback",
                "from_mode": previous_mode,
                "to_mode": "backend",
                "reason": str(exc),
            }
        )
        return True

    def _execute_job(self, primitive: str, submit: Callable[[], Any]) -> Any:
        entry: dict[str, Any] = {
            "primitive": primitive,
            "selected_mode": self.plan.selected_mode,
            "submitted_at_epoch": time.time(),
        }
        try:
            job = submit()
        except Exception as exc:
            entry["status"] = "submit_failed"
            entry["error"] = str(exc)
            self.job_log.append(entry)
            raise
        job_id_attr = getattr(job, "job_id", None)
        if callable(job_id_attr):
            try:
                entry["job_id"] = job_id_attr()
            except Exception:
                pass
        elif job_id_attr is not None:
            entry["job_id"] = str(job_id_attr)
        try:
            result = job.result()
        except Exception as exc:
            entry["status"] = "failed"
            entry["error"] = str(exc)
            entry["finished_at_epoch"] = time.time()
            self.job_log.append(entry)
            raise
        entry["status"] = "completed"
        entry["finished_at_epoch"] = time.time()
        self.job_log.append(entry)
        return result

    def _run_with_recovery(self, fn: Callable[[], Any]) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, self.cfg.runtime_retry_attempts + 1):
            try:
                return fn()
            except Exception as exc:  # pragma: no cover - exercised with monkeypatch/unit mocks
                last_exc = exc
                if self._fallback_to_backend(exc):
                    self.refresh()
                    continue
                if attempt >= self.cfg.runtime_retry_attempts or not self._is_recoverable(exc):
                    raise
                self.refresh()
                if self.cfg.runtime_retry_backoff_seconds > 0.0:
                    time.sleep(self.cfg.runtime_retry_backoff_seconds * max(1, attempt - 1))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Runtime execution failed without an exception.")

    def run_estimator(self, pubs: list[Any]) -> Any:
        self.ensure_open()
        return self._run_with_recovery(lambda: self._execute_job("estimator", lambda: self.estimator.run(pubs)))

    def run_sampler(self, pubs: list[Any]) -> Any:
        self.ensure_open()
        return self._run_with_recovery(lambda: self._execute_job("sampler", lambda: self.sampler.run(pubs)))

    def metadata(self) -> dict[str, Any]:
        payload = self.plan.as_dict()
        payload["recovery_events"] = list(self.recovery_events)
        payload["job_log"] = list(self.job_log)
        return payload

__all__ = [
    'RuntimeSupportStatus',
    'RuntimeExecutionPlan',
    'RECOVERABLE_RUNTIME_ERRORS',
    'runtime_status',
    'RuntimeSamplerFactory',
    'RuntimeSessionManager',
]
