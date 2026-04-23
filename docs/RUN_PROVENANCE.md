# Run Provenance

This file records how to describe benchmark timing and scope for the **post-pivot J1-J2 Ising study layer**.

## What To Record For Every Bundle

- run date and time zone
- backend: `local_proxy`, `aer`, or live IBM Runtime
- execution mode if live runtime is used
- exact study grid:
  - `n_spins`
  - `magnetization_m`
  - `J2/J1`
  - `disorder_strength`
  - depth
  - shot budgets
  - noise levels
  - seeds
- artifact manifest path
- total trial count and total recorded outcomes

## Why This Matters

The repository is intended for thesis-grade benchmarking. A reviewer should be able to ask:

- when was this run produced?
- what exact grid did it cover?
- which backend generated it?
- is this the main evidence bundle or an appendix?

and get an answer directly from the artifact set.

## Recommended Labels

- `pilot_local_proxy`
- `pilot_aer`
- `compact_j2_sweep_local_proxy`
- `compact_j2_sweep_aer`
- `live_appendix_backend`

## Historical Note

Earlier pre-pivot benchmark bundles remain in `results/` for provenance, but they should be treated as archived iteration history rather than the active physics-facing evidence layer.
