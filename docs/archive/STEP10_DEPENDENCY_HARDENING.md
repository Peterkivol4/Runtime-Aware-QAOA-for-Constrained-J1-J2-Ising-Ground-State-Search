# Step 10 — dependency surface tightening

This pass focused on import-time dependency reduction and dependency-surface documentation.

## Changes

- moved the optional `torch` import in `logging_utils.py` behind a function-local import
- moved the optional `mlflow` import in `tracking.py` behind the MLflow sink path
- added `DEPENDENCY_SURFACE.md`
- added `requirements-lock.txt` from the validation environment
- added `tools/dependency_surface.py`

## Reduced baseline

The same reduced smoke baseline was re-run after this pass and still returned:

- `success = True`
- `best_energy = exact_energy = -0.27263459418542246`
- `valid_ratio = 0.2604166666666667`
- `measurement_success_probability = 0.07291666666666667`
