# Scaling Audit Report

- observed_at: `2026-04-13T23:49:41+08:00`
- runtime_mode: `local_proxy`
- tested n_assets values: `[4, 6, 8, 10, 12, 14]`
- max completed n_assets: `14`
- mean runtime seconds: `0.1318059762318929`
- max runtime seconds: `0.4378046989440918`
- mean valid ratio: `0.3020833333333333`
- min valid ratio: `0.21875`

## Assessment

- applicable_for_tested_scale: `True`
- takeaway: The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_assets.

## Rows

- n=4 | state_space=16 | runtime=0.4378s | valid_ratio=0.3438 | P_succ=0.2500
- n=6 | state_space=64 | runtime=0.0013s | valid_ratio=0.3125 | P_succ=0.1250
- n=8 | state_space=256 | runtime=0.0037s | valid_ratio=0.2812 | P_succ=0.0938
- n=10 | state_space=1024 | runtime=0.0150s | valid_ratio=0.3438 | P_succ=0.0938
- n=12 | state_space=4096 | runtime=0.0653s | valid_ratio=0.3125 | P_succ=0.0000
- n=14 | state_space=16384 | runtime=0.2676s | valid_ratio=0.2188 | P_succ=0.0000
