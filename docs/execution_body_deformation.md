# Execution-Body Deformation

SpinMesh Runtime studies QAOA as a physical instrument running through a real execution body. The same Hamiltonian, ansatz, and optimized angles can produce different physical conclusions after routing, backend topology, calibration age, queue delay, shot budget, session policy, and mitigation are applied.

The central claim is deliberately stronger than runtime accounting:

> Runtime is not only cost. Runtime is a physical deformation channel.

## Research question

For a fixed frustrated-spin QAOA problem, when do runtime conditions change the physical conclusion of the experiment: energy ranking, magnetization, correlations, phase identification, or quantum-vs-classical decision, even if the source-level circuit and optimizer are unchanged?

Equivalently:

> When does execution context become part of the physical experiment?

## Physical model

The source-level spin model remains the constrained J1-J2 Ising system:

```text
H = -J1 sum_i Z_i Z_{i+1} - J2 sum_i Z_i Z_{i+2} - h sum_i X_i
```

SpinMesh records the observed runtime result as:

```text
R_obs = X_{B,t,S,M}(|psi_p(gamma, beta)>)
```

where:

| Symbol | Meaning |
| --- | --- |
| `B` | backend topology or device |
| `t` | calibration time, calibration age, and queue delay |
| `S` | shot budget and session policy |
| `M` | mitigation and measurement-correction policy |
| `X` | execution-body deformation channel |

The scientific object is therefore not only the ideal QAOA state. It is the QAOA state after routing, drift, finite shots, topology constraints, and runtime policy.

## Scientific record

The core record is `ExecutionDeformationVector` in `spinmesh_runtime.execution_body`. It captures:

- problem identity, backend identity, and calibration snapshot identity
- source depth, transpiled depth, two-qubit gate count, swap count, and layout-distance score
- shot budget, queue delay, session duration, and calibration age
- energy, magnetization, correlation, structure-factor, and phase-label deformation
- sample variance, confidence interval width, mitigation shift, and mitigation instability
- runtime decision and rejection reason

This record turns runtime instrumentation into physics data. Routing is connected to observable error. Calibration age is connected to drift. Shots are connected to conclusion stability. Mitigation is treated as a transformation that can improve or distort the result.

## Runtime trust gate

`RuntimeTrustGate` is the scientific governor. It accepts, warns, or rejects a quantum result according to explicit thresholds:

- maximum calibration age
- maximum depth or two-qubit routing inflation
- maximum confidence-interval width
- maximum mitigation shift
- maximum observable error
- whether a classical baseline is required

Canonical rejection reasons are:

- `runtime.reject.calibration_stale`
- `runtime.reject.routing_deformed`
- `runtime.reject.shot_unstable`
- `runtime.reject.mitigation_unstable`
- `runtime.reject.classical_dominates`

The point is not to hide failed quantum runs. The point is to explain which execution body caused the result to lose physical trust.

## Executed compact experiment

The compact execution-body sweep is implemented in `tools/run_execution_body_experiments.py` and can be reproduced with:

```bash
PYTHONPATH=src python tools/run_execution_body_experiments.py --output-dir results/execution_body
```

The executed instance fixes the Hamiltonian, QAOA depth, seed, and optimized angles:

- problem id: `frustrated_n6_j2_05_p2_seed314`
- lattice: `j1j2_frustrated`
- `n_spins = 6`
- `J2/J1 = 0.5`
- magnetization sector: `M = 0`
- QAOA depth: `p = 2`
- source circuit depth before backend lowering: `18`
- frozen source-level phase label: `nearest_neighbor_antiferromagnetic`

The run writes `90` `ExecutionDeformationVector` records and executes all six experiment families below. In the frozen-circuit routing sweep, the same abstract circuit produced transpiled depths from `378` to `1568` and two-qubit gate counts from `96` to `400`; two-qubit gate count correlated with correlation error at `r ~= 0.60` and with valid-sector ratio at `r ~= -0.64`. The trust gate rejected all compact quantum records, primarily because routing inflation was already too high to treat the noisy physical conclusion as trustworthy.

## Frustration-axis valid-ratio control

The fine-axis control in `results/frustration_axis/` fixes `n_spins = 8`, QAOA depth `p = 2`, final-readout shots `256`, and sweeps `J2/J1` from `0.0` to `1.0` in `0.1` increments. Under the clean local-proxy Dicke/XY path, valid-sector ratio does not collapse below `0.5`; the all-method mean at `J2/J1 = 0.5` is `0.8783`.

The routed Aer control in `results/frustration_axis_aer/` uses the same fine axis with a fixed six-spin routed execution body. It does reproduce sector collapse, but the collapse is broad rather than centered at `J2/J1 = 0.5`: the mean valid ratio at `0.5` is `0.3166`, compared with an endpoint mean of `0.3154`.

This narrows the current claim. The strongest evidence is not that the fixed-sector ansatz intrinsically collapses fastest exactly at the maximally frustrated point; it is that the execution body can dominate fixed-sector leakage strongly enough to flatten the frustration-axis dependence.

## First experiment roadmap

### 1. Frozen-circuit, changing-execution study

Fix the Hamiltonian, optimized angles, seed, depth, and shot count. Vary transpiler optimization level, initial layout, topology model, and routing strategy. Measure transpiled depth, two-qubit gate count, swap count, energy error, magnetization error, and correlation error.

Main question: does routing deformation change measured physics even when the abstract circuit is identical?

### 2. Calibration-age deformation

Compare fresh, delayed, and historical calibration snapshots for the same backend and circuit family. Measure T1/T2 drift, gate-error drift, readout-error drift, predicted observable drift, observed observable drift, and trust-gate decision changes.

Main question: at what calibration age does the QAOA result stop being physically interpretable?

### 3. Shot-body deformation

Sweep shots over `128, 256, 512, 1024, 4096, 8192`. Measure energy confidence intervals, magnetization confidence intervals, correlation confidence intervals, phase-label stability, optimizer-decision stability, and quantum-vs-classical decision stability.

Main question: how many shots are needed before the physical conclusion stabilizes?

### 4. Session-body deformation

Compare equivalent circuits run in one session, split across time, grouped by observable, and randomized across groups. Measure within-session drift, between-session drift, observable consistency, mitigation consistency, and decision consistency.

Main question: does session policy change the measured physical state?

### 5. Mitigation-body deformation

Compare no mitigation, readout mitigation, zero-noise extrapolation, calibration correction, and bootstrap-resampled mitigation. Measure mitigation shift, mitigation instability, observable improvement, and false correction cases.

Main question: does mitigation improve the physical conclusion or only improve the energy number?

### 6. Runtime decision boundary

Classify each run as accepted, accepted with warning, or rejected for calibration, routing, shot, mitigation, or classical-dominance reasons.

Main question: when does QAOA remain physically interpretable, and when should classical baselines be preferred because the execution body has deformed the result too much?

## Output contract

Execution-body studies should write:

```text
results/execution_body/
  execution_deformation_records.csv
  execution_deformation_summary.json
  routing_deformation_report.md
  calibration_freshness_threshold.md
  shot_body_stability_report.md
  session_drift_report.md
  mitigation_deformation_report.md
  runtime_decision_boundary.md
  classical_vs_quantum_stability.md
```

The most important artifact is `runtime_decision_boundary.md`, because it states which runtime body changed the trust decision and why.

## Separation from depth-scaling studies

Depth-scaling asks what the ansatz can represent as `p` changes. Execution-body deformation asks what happens after a fixed ansatz enters the execution stack. Many SpinMesh Runtime experiments should therefore hold `p`, angles, Hamiltonian, and seed fixed while varying routing, topology, calibration age, shots, session policy, or mitigation.

That separation keeps this repo focused on physical execution context rather than ansatz expressivity.
