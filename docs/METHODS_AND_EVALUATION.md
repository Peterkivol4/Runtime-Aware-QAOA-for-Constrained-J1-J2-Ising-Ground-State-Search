# Methods And Evaluation

## Research question

The core question is:

> Under realistic NISQ execution constraints, when does runtime-aware QAOA improve constrained J1-J2 Ising ground-state approximation quality relative to strong classical baselines?

## Problem setting

The benchmark solves fixed-magnetization Ising instances with:

- system size `n_spins`
- magnetization sector `sum_i sigma_i = M`
- lattice family `lattice_type`
- couplings `j1_coupling`, `j2_coupling`, `disorder_strength`, and optional `h_field`
- exact fixed-sector references on small enough systems for direct approximation-gap measurement

The binary encoding uses `sigma_i = 2 x_i - 1`, which maps the fixed magnetization sector onto a fixed-cardinality sector `sum_i x_i = k = (M + N) / 2`.

## Solver families

The study compares:

- classical baselines: exact search, local-field greedy, local search, simulated annealing, random feasible search, and a classical BO-style surrogate
- quantum variants: BO-tuned Fourier QAOA, SPSA-tuned Fourier QAOA, random-search Fourier QAOA, and BO-tuned direct-angle QAOA
- mitigation bundles: none, readout only, and readout plus ZNE

## Runtime-aware factors

The implementation keeps execution realism explicit:

- shot budgets and dynamic-shot behavior
- mitigation overhead
- estimator-versus-sampler separation
- checkpoint and resume behavior
- backend/session controls
- utility scoring that folds quality, runtime cost, and total shots into an execution recommendation

## Primary benchmark questions

1. Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency for frustrated ground-state search?
2. Does readout mitigation plus ZNE materially improve quality near the maximally frustrated region around `J2/J1 = 0.5`?
3. How does valid-sector ratio collapse as system size, depth, and frustration increase?

## Primary metrics

- approximation gap relative to the exact fixed-sector optimum
- approximation ratio
- valid-sector ratio
- measurement success probability
- runtime seconds
- total shots
- objective calls and runtime per call
- performance profiles
- cost-normalized utility frontier

## Artifact mapping

- `*_summary.csv`: per-trial record table
- `*_aggregates.csv`: grouped statistics used for tables
- `*_findings.md`: machine-generated narrative summary
- `*_executive_summary.md`: high-level synthesis
- `*_utility_frontier.csv`: cost-normalized ranking of execution candidates
- `*_decision_report.json`: structured recommendation payload
- `*_energy_gap_vs_j2_ratio.png`: hardness landscape over `J2/J1`
- `*_valid_ratio_vs_depth.png` and `*_valid_sector_ratio_vs_spins.png`: sector-failure behavior
- `*_success_vs_noise.png`: backend/noise sensitivity

## Threats to validity

- local-proxy and Aer results are not the same as real hardware evidence
- exact fixed-sector references limit the largest tractable systems
- utility rankings depend on the chosen runtime and shot weights
- negative or flat results on shallow instances must be reported honestly rather than hidden
