# Step 11 — lazy import hardening

This pass reduces import-time exposure for optional analysis dependencies without changing the benchmark math or the reduced smoke-path behavior.

Changes:
- added `ionmesh_runtime._internal.optional_deps`
- moved `pandas` loading behind a helper in:
  - decision
  - market_data
  - plotting
  - tracking
  - pipeline
- moved `matplotlib.pyplot` loading behind a helper in plotting
- moved `scipy.stats.mannwhitneyu` loading behind a helper in pipeline
- added public wrappers for `optional_deps`

Why:
- lower import-time dependency surface
- fail later and with operator-safe messages only when optional reporting/data functionality is actually used
- keep the smoke/runtime path from pulling analysis dependencies earlier than needed

Reduced baseline after this pass:
- success=True
- best_energy=-0.27263459418542246
- exact_energy=-0.27263459418542246
- valid_ratio=0.2604166666666667
- measurement_success_probability=0.07291666666666667
