# Live IBM Hardware Protocol

This repository should only be described as having **live IBM hardware evidence** when all of the following are true:

1. The run executed on a real backend with `simulator=False` and `operational=True`.
2. The runtime path used the production runtime stack for optimization and final readout on ISA-transpiled circuits.
3. The artifact bundle records backend metadata, shot accounting, and enough configuration detail to reproduce the same cell on Aer or `local_proxy`.

## Required Evidence

- backend name, queue state, and execution mode
- runtime job identifiers
- transpilation metadata and basis-gate audit
- shot accounting for optimization and final readout
- the exact lattice cell:
  - `lattice_type`
  - `n_spins`
  - `magnetization_m`
  - `J2/J1`
  - `disorder_strength`
- a paired simulator comparison when possible

## Recommended Command

```bash
python -m spinmesh_runtime.cli \
  --mode live_cert \
  --runtime-mode runtime_v2 \
  --runtime-backend ibm_brisbane \
  --runtime-execution-mode backend \
  --output-prefix results/live_hardware/live_cert
```

Then run a small live validation suite with at least:

- two hardware repeats
- two matched Aer repeats
- one appendix sweep over either a second `J2/J1` point or a second `n_spins` value

Do not treat a single successful job as a full hardware study. Treat it as appendix evidence unless the grid is large enough to support the thesis claim directly.
