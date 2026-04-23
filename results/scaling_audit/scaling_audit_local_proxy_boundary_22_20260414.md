# Scaling Audit Report

- observed_at: `2026-04-14T00:10:30+08:00`
- runtime_mode: `local_proxy`
- tested n_assets values: `[22]`
- max completed n_assets: `22`
- mean runtime seconds: `89.53404307365417`
- max runtime seconds: `89.53404307365417`
- mean valid ratio: `0.21875`
- min valid ratio: `0.21875`

## Assessment

- applicable_for_tested_scale: `True`
- takeaway: The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_assets.

## Rows

- n=22 | state_space=4194304 | runtime=89.5340s | valid_ratio=0.2188 | P_succ=0.0000
