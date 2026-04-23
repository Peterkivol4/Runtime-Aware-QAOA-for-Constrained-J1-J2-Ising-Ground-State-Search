# Scaling Audit Report

- observed_at: `2026-04-13T23:50:14+08:00`
- runtime_mode: `aer`
- tested n_assets values: `[12]`
- max completed n_assets: `12`
- mean runtime seconds: `0.5726771354675293`
- max runtime seconds: `0.5726771354675293`
- mean valid ratio: `1.0`
- min valid ratio: `1.0`

## Assessment

- applicable_for_tested_scale: `True`
- takeaway: The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_assets.

## Rows

- n=12 | state_space=4096 | runtime=0.5727s | valid_ratio=1.0000 | P_succ=0.0000
