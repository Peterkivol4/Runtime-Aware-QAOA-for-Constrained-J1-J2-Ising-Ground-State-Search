# Methods And Evaluation

## Research question

The core question is:

> For a fixed frustrated-spin QAOA problem, when do execution-body conditions change the measured physical conclusion or make the quantum result less trustworthy than a classical fixed-sector baseline?

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

## Execution-body factors

The implementation keeps execution realism explicit:

- routing, topology, initial layout, and transpiler optimization level
- calibration age and backend noise snapshots
- shot budgets and dynamic-shot behavior
- session policy and queue delay
- mitigation overhead
- estimator-versus-sampler separation
- checkpoint and resume behavior
- utility scoring that folds quality, runtime cost, and total shots into an execution recommendation

## Primary benchmark questions

1. Does routing deformation change measured observables when the source QAOA circuit is fixed?
2. Does calibration, finite shots, session policy, or mitigation restore or further deform physical trust?
3. Does valid-sector ratio collapse intrinsically across `J2/J1`, or mainly after routed/noisy execution?

## Primary metrics

- approximation gap relative to the exact fixed-sector optimum
- approximation ratio
- valid-sector ratio
- measurement success probability
- runtime seconds
- total shots
- objective calls and runtime per call
- routing inflation and two-qubit gate count
- confidence interval width
- mitigation shift and mitigation instability
- trust-gate decision and rejection reason

## Artifact mapping

- `results/execution_body/execution_deformation_records.csv`: execution-body record table
- `results/execution_body/runtime_decision_boundary.md`: trust-gate decisions
- `results/execution_body/routing_deformation_report.md`: fixed-circuit routing analysis
- `results/frustration_axis/frustration_axis_valid_ratio_aggregates.csv`: clean `J2/J1` valid-sector control
- `results/frustration_axis_aer/frustration_axis_aer_aggregates.csv`: routed Aer valid-sector control

## Threats to validity

- local-proxy and Aer results are not the same as real hardware evidence
- exact fixed-sector references limit the largest tractable systems
- utility rankings depend on the chosen runtime and shot weights
- negative or flat results on shallow instances must be reported honestly rather than hidden
