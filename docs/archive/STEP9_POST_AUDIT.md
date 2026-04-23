# Step 9 — post-audit tightening

This pass was applied after the Step 8 reduced-scope audit to close a few low-risk residual items without changing benchmark behavior.

## Changes

- removed packaged `__pycache__` / `.pyc` artifacts from the staged tree
- added `safe_errors.py` with an operator-safe error wrapper
- routed runtime credential failure through the safe error wrapper
- centralized additional support defaults:
  - bootstrap seed
  - market-template defaults
  - runtime/operator messages
- moved the pipeline bootstrap RNG seed out of logic-local scope
- moved market template defaults out of `market_data.py`

## Reduced baseline

The same reduced smoke baseline was re-run after this pass and still returned:

- `success = True`
- `best_energy = exact_energy = -0.27263459418542246`
- `valid_ratio = 0.2604166666666667`
- `measurement_success_probability = 0.07291666666666667`

## Scope note

This remains a reduced-scope hardening continuation against the private build, not a full enterprise equivalence program.
