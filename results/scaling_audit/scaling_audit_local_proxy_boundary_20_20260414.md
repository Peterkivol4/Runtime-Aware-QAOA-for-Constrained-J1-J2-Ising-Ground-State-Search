# Scaling Audit Report

- observed_at: `2026-04-14T00:08:37+08:00`
- runtime_mode: `local_proxy`
- tested n_assets values: `[20]`
- max completed n_assets: `20`
- mean runtime seconds: `21.642863750457764`
- max runtime seconds: `21.642863750457764`
- mean valid ratio: `0.1875`
- min valid ratio: `0.1875`

## Assessment

- applicable_for_tested_scale: `True`
- takeaway: The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_assets.

## Rows

- n=20 | state_space=1048576 | runtime=21.6429s | valid_ratio=0.1875 | P_succ=0.0000
