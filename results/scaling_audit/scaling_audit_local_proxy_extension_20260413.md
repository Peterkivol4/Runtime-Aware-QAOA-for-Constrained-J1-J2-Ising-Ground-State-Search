# Scaling Audit Report

- observed_at: `2026-04-13T23:50:20+08:00`
- runtime_mode: `local_proxy`
- tested n_assets values: `[16, 18]`
- max completed n_assets: `18`
- mean runtime seconds: `3.2779035568237305`
- max runtime seconds: `5.014376163482666`
- mean valid ratio: `0.15625`
- min valid ratio: `0.125`

## Assessment

- applicable_for_tested_scale: `True`
- takeaway: The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_assets.

## Rows

- n=16 | state_space=65536 | runtime=1.5414s | valid_ratio=0.1250 | P_succ=0.0000
- n=18 | state_space=262144 | runtime=5.0144s | valid_ratio=0.1875 | P_succ=0.0000
