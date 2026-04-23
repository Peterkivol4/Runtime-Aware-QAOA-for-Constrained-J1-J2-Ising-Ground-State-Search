# Dependency surface

This private build keeps the runtime dependency set intentionally small.

## Runtime dependencies

- `numpy` — vector math, sampling, portfolio objective evaluation
- `scipy` — statistical helpers used in optimization/reporting
- `scikit-learn` — Gaussian-process surrogate for BO tuning
- `pandas` — tabular study output, CSV/SQLite interchange, market data windows
- `matplotlib` — offline figure generation only

## Optional runtime integrations

These are discovered lazily and are not required to import or run the local smoke path.

- `qiskit`, `qiskit-aer`, `qiskit-ibm-runtime` — quantum execution paths
- `mlflow` — optional experiment sink when tracker backend is `mlflow` or `both`
- `torch` — optional reproducibility seed hook when present

## Dev-only dependencies

- `pytest`
- `pytest-cov`
- `ruff`
- `build`

## Hardening notes

- Optional integrations are imported at use sites rather than module import time.
- The reduced smoke baseline does not require Qiskit, MLflow, or Torch.
- The private build keeps fallback behavior for environments without compiled native support.
