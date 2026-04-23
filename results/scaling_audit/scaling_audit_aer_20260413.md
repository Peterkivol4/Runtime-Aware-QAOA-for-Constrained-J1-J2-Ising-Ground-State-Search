# Scaling Audit Report

- observed_at: `2026-04-13T23:49:41+08:00`
- runtime_mode: `aer`
- tested n_assets values: `[4, 6, 8, 10]`
- max completed n_assets: `10`
- mean runtime seconds: `0.19522607326507568`
- max runtime seconds: `0.5469751358032227`
- mean valid ratio: `1.0`
- min valid ratio: `1.0`

## Assessment

- applicable_for_tested_scale: `True`
- takeaway: The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_assets.

## Rows

- n=4 | state_space=16 | runtime=0.5470s | valid_ratio=1.0000 | P_succ=1.0000
- n=6 | state_space=64 | runtime=0.0750s | valid_ratio=1.0000 | P_succ=0.0000
- n=8 | state_space=256 | runtime=0.0733s | valid_ratio=1.0000 | P_succ=0.0000
- n=10 | state_space=1024 | runtime=0.0856s | valid_ratio=1.0000 | P_succ=0.0000
