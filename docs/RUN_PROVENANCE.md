# Run Provenance

This file records how to describe timing and scope for the **SpinMesh Runtime execution-body evidence layer**.

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
- artifact manifest or summary path
- total record count and total aggregate rows

## Why This Matters

The repository is intended for thesis-grade benchmarking. A reviewer should be able to ask:

- when was this run produced?
- what exact grid did it cover?
- which backend generated it?
- is this the main evidence bundle or an appendix?

and get an answer directly from the artifact set.

## Recommended Labels

- `execution_body_fixed_circuit`
- `frustration_axis_local_proxy`
- `frustration_axis_routed_aer`
- `live_appendix_backend`

## Historical Note

Earlier pre-pivot benchmark bundles were removed from the public result surface. Keep only artifacts that directly support the current execution-body deformation claim.
