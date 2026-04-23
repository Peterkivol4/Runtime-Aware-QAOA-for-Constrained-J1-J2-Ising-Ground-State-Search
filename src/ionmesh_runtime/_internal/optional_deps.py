from __future__ import annotations

from importlib import import_module

from .safe_errors import safe_error

__all__ = [
    "load_matplotlib_pyplot",
    "load_pandas",
    "load_mannwhitneyu",
    "load_sobol_tools",
    "load_gp_tools",
    "load_qiskit_core",
    "load_qiskit_aer",
    "load_qiskit_fake_backend",
    "load_qiskit_runtime_v2",
]


def _load(mod_name: str, attr: str | None, code: str, msg: str):
    try:
        mod = import_module(mod_name)
    except Exception as exc:
        raise safe_error(code, msg, debug_detail=f"{mod_name}: {exc!r}") from exc
    if attr is None:
        return mod
    try:
        return getattr(mod, attr)
    except AttributeError as exc:
        raise safe_error(code, msg, debug_detail=f"{mod_name}.{attr}: {exc!r}") from exc


def load_pandas():
    return _load("pandas", None, "optional-pandas-missing", "pandas support is unavailable in this environment")


def load_matplotlib_pyplot():
    return _load("matplotlib.pyplot", None, "optional-matplotlib-missing", "plotting support is unavailable in this environment")


def load_mannwhitneyu():
    stats = _load("scipy.stats", None, "optional-scipy-missing", "statistical reporting support is unavailable in this environment")
    return getattr(stats, "mannwhitneyu")


def load_sobol_tools():
    qmc = _load("scipy.stats.qmc", None, "optional-scipy-missing", "Sobol sampling support is unavailable in this environment")
    return qmc


def load_gp_tools():
    sklearn_gp = _load(
        "sklearn.gaussian_process",
        None,
        "optional-sklearn-missing",
        "Gaussian-process tuning support is unavailable in this environment",
    )
    kernels = _load(
        "sklearn.gaussian_process.kernels",
        None,
        "optional-sklearn-missing",
        "Gaussian-process tuning support is unavailable in this environment",
    )
    exc_mod = _load(
        "sklearn.exceptions",
        None,
        "optional-sklearn-missing",
        "Gaussian-process tuning support is unavailable in this environment",
    )
    return {
        "GaussianProcessRegressor": getattr(sklearn_gp, "GaussianProcessRegressor"),
        "ConstantKernel": getattr(kernels, "ConstantKernel"),
        "Matern": getattr(kernels, "Matern"),
        "WhiteKernel": getattr(kernels, "WhiteKernel"),
        "ConvergenceWarning": getattr(exc_mod, "ConvergenceWarning"),
    }


def load_qiskit_core():
    circuit = _load(
        "qiskit.circuit",
        None,
        "optional-qiskit-missing",
        "qiskit circuit support is unavailable in this environment",
    )
    library = _load(
        "qiskit.circuit.library",
        None,
        "optional-qiskit-missing",
        "qiskit circuit library support is unavailable in this environment",
    )
    quant = _load(
        "qiskit.quantum_info",
        None,
        "optional-qiskit-missing",
        "qiskit quantum info support is unavailable in this environment",
    )
    prim = _load(
        "qiskit.primitives",
        None,
        "optional-qiskit-missing",
        "qiskit primitive support is unavailable in this environment",
    )
    pm = _load(
        "qiskit.transpiler.preset_passmanagers",
        None,
        "optional-qiskit-missing",
        "qiskit transpiler support is unavailable in this environment",
    )
    qiskit = _load(
        "qiskit",
        None,
        "optional-qiskit-missing",
        "qiskit support is unavailable in this environment",
    )
    return {
        "QuantumCircuit": getattr(qiskit, "QuantumCircuit"),
        "ParameterVector": getattr(circuit, "ParameterVector"),
        "StatePreparation": getattr(library, "StatePreparation"),
        "BackendSamplerV2": getattr(prim, "BackendSamplerV2"),
        "Operator": getattr(quant, "Operator"),
        "SparsePauliOp": getattr(quant, "SparsePauliOp"),
        "generate_preset_pass_manager": getattr(pm, "generate_preset_pass_manager"),
    }


def load_qiskit_aer():
    aer = _load(
        "qiskit_aer",
        None,
        "optional-qiskit-aer-missing",
        "qiskit-aer support is unavailable in this environment",
    )
    noise = _load(
        "qiskit_aer.noise",
        None,
        "optional-qiskit-aer-missing",
        "qiskit-aer noise support is unavailable in this environment",
    )
    return {
        "AerSimulator": getattr(aer, "AerSimulator"),
        "NoiseModel": getattr(noise, "NoiseModel"),
        "ReadoutError": getattr(noise, "ReadoutError"),
        "depolarizing_error": getattr(noise, "depolarizing_error"),
        "thermal_relaxation_error": getattr(noise, "thermal_relaxation_error"),
    }


def load_qiskit_fake_backend():
    fake = _load(
        "qiskit.providers.fake_provider",
        None,
        "optional-qiskit-fake-backend-missing",
        "qiskit fake backend support is unavailable in this environment",
    )
    pm = _load(
        "qiskit.transpiler.preset_passmanagers",
        None,
        "optional-qiskit-missing",
        "qiskit transpiler support is unavailable in this environment",
    )
    return {
        "GenericBackendV2": getattr(fake, "GenericBackendV2"),
        "generate_preset_pass_manager": getattr(pm, "generate_preset_pass_manager"),
    }


def load_qiskit_runtime_v2():
    runtime = _load(
        "qiskit_ibm_runtime",
        None,
        "optional-runtime-missing",
        "IBM Runtime support is unavailable in this environment",
    )
    exc_mod = _load(
        "qiskit_ibm_runtime.exceptions",
        None,
        "optional-runtime-missing",
        "IBM Runtime support is unavailable in this environment",
    )
    return {
        "Batch": getattr(runtime, "Batch"),
        "EstimatorV2": getattr(runtime, "EstimatorV2"),
        "QiskitRuntimeService": getattr(runtime, "QiskitRuntimeService"),
        "SamplerV2": getattr(runtime, "SamplerV2"),
        "Session": getattr(runtime, "Session"),
        "IBMRuntimeError": getattr(exc_mod, "IBMRuntimeError", Exception),
        "IBMRestRuntimeError": getattr(exc_mod, "IBMRestRuntimeError", getattr(exc_mod, "IBMRuntimeError", Exception)),
        "IBMRuntimeApiError": getattr(exc_mod, "IBMRuntimeApiError", getattr(exc_mod, "IBMApiError", getattr(exc_mod, "IBMRuntimeError", Exception))),
        "IBMRuntimeJobFailureError": getattr(exc_mod, "IBMRuntimeJobFailureError", getattr(exc_mod, "IBMBackendError", getattr(exc_mod, "IBMRuntimeError", Exception))),
    }
