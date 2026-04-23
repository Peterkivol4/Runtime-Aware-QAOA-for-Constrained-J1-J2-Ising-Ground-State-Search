# Scaling Audit Timeout Note

- observed_at: `2026-04-14T00:15:00+08:00`
- runtime_mode: `local_proxy`
- n_assets: `24`
- budget: `12`
- depth: `1`
- base_shots: `32`
- state_space_size: `16777216`
- feasible_space_size: `2704156`
- status: `interrupted_after_practical_guard_window`

## Interpretation

- The direct `n=24` smoke probe remained running for more than five minutes and was manually terminated.
- Combined with the completed `n=22` cell at about `89.53s`, this suggests the current implementation remains operational through `n=22` on this machine but is no longer practically usable for iterative study at `n=24`.
