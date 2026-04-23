# Scaling Audit Report

- observed_at: `2026-04-21T01:21:44+08:00`
- runtime_mode: `local_proxy`
- tested n_spins values: `[4, 6, 8, 10, 12, 14]`
- max completed n_spins: `14`
- mean runtime seconds: `0.72914191087087`
- max runtime seconds: `3.2758469581604004`
- mean valid ratio: `0.9322916666666666`
- min valid ratio: `0.875`

## Assessment

- applicable_for_tested_scale: `True`
- takeaway: The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_spins.

## Rows

- n=4 | state_space=16 | runtime=0.2796s | valid_ratio=1.0000 | P_succ=0.9375
- n=6 | state_space=64 | runtime=0.0050s | valid_ratio=0.9062 | P_succ=0.9062
- n=8 | state_space=256 | runtime=0.0249s | valid_ratio=0.9688 | P_succ=0.7500
- n=10 | state_space=1024 | runtime=0.1301s | valid_ratio=0.8750 | P_succ=0.7812
- n=12 | state_space=4096 | runtime=0.6594s | valid_ratio=0.9062 | P_succ=0.7500
- n=14 | state_space=16384 | runtime=3.2758s | valid_ratio=0.9375 | P_succ=0.4375
