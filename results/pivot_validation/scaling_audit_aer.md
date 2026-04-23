# Scaling Audit Report

- observed_at: `2026-04-21T01:22:37+08:00`
- runtime_mode: `aer`
- tested n_spins values: `[4, 6, 8, 10]`
- max completed n_spins: `10`
- mean runtime seconds: `0.24806421995162964`
- max runtime seconds: `0.4393882751464844`
- mean valid ratio: `1.0`
- min valid ratio: `1.0`

## Assessment

- applicable_for_tested_scale: `True`
- takeaway: The current implementation completed every tested cell, but the exact-state-space bookkeeping still scales exponentially in n_spins.

## Rows

- n=4 | state_space=16 | runtime=0.4394s | valid_ratio=1.0000 | P_succ=0.3125
- n=6 | state_space=64 | runtime=0.0731s | valid_ratio=1.0000 | P_succ=0.0938
- n=8 | state_space=256 | runtime=0.1231s | valid_ratio=1.0000 | P_succ=0.0000
- n=10 | state_space=1024 | runtime=0.3567s | valid_ratio=1.0000 | P_succ=0.0000
