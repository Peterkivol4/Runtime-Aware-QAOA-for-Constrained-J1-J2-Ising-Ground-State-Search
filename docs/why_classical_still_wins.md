# Why Classical Still Wins on One Concrete J1-J2 Workload

This note exists for one reason: the most useful outcome of an execution-body benchmark is often a decision not to spend more quantum budget.

## Workload

The case below comes from the current execution-body and routed Aer controls in `results/execution_body/` and `results/frustration_axis_aer/`.

- lattice: `j1j2_frustrated`
- size: `n_spins = 6`
- magnetization sector: half-filling (`M = 0`, so `k = 3`)
- frustration ratio: `J2/J1 = 0.5`
- disorder strength: `0.0`
- execution body: routed Aer-style backend with `forked_heavy_hex` topology and `sabre` routing

This is a clean, small, maximally frustrated test case. It is exactly the sort of workload where a shallow, symmetry-matched QAOA pass is tempting.

## Budget and setup

The concrete comparison that mattered most was the compact routed execution body that still looked operationally plausible:

- backend path: routed `AerSimulator`
- QAOA depth: `p = 2`
- shot budget: `2048`
- topology: `forked_heavy_hex`
- routing method: `sabre`
- transpiler optimization level: `1`

The baseline reference on the same workload was `exact_feasible`.

## What we expected

The expectation was modest, not grandiose. With Dicke-state initialization, a fixed-magnetization sector, and a small six-spin instance, a low-budget QAOA run could plausibly have been worth trying even if it did not beat the classical optimum outright.

The bar was therefore not "prove quantum advantage." The bar was "preserve enough valid-sector mass, at low enough operational cost, that a quantum-first recommendation is defensible."

## What failed

The clean local-proxy path did not intrinsically collapse at the frustration point: the fine sweep reports a mean valid-sector ratio of `0.8783` at `J2/J1 = 0.5`. The routed Aer control tells a different story. At the same nominal frustration point, the routed execution body reports:

- `mean_valid_ratio = 0.3166`
- `collapse_fraction = 1.0`
- `mean_correlation_error = 0.4006`
- `mean_routing_inflation = 33.5926`
- `mean_two_qubit_gate_count = 196`

In other words, the source-level circuit and the physics problem were not enough to preserve sector trust after routing and noisy execution. Only about one third of measured mass stayed in the valid magnetization sector.

The broader execution-body sweep found the same failure mode under a fixed source circuit:

- `90 / 90` quantum records were rejected by the compact trust gate
- transpiled depth ranged from `378` to `1568`
- two-qubit gate count ranged from `96` to `400`
- two-qubit gate count correlated with correlation error at approximately `r = 0.60`

Mitigation also did not rescue the compact case. The mitigation report flags a false-correction case where ZNE improved energy error while worsening correlation error.

## Why the classical recommendation survived

The same compact workload has an exact fixed-sector classical reference:

- exact feasible energy: `-5.00000000`
- exact feasible bitstring: `101010`
- valid-sector ratio: `1.0`
- shots: `0`

This is the concrete reason the decision layer remains useful. If we looked only at energy, the shallow QAOA run would appear more usable than it really is. The framework prevents that mistake by charging QAOA for the thing that matters operationally: how much valid, decision-usable probability mass survives after routing, noise, and finite-shot execution.

For this workload, the classical recommendation survived because QAOA bought no decision-quality gain. It bought routed two-qubit depth, finite-shot uncertainty, and mitigation ambiguity while still leaving most of the sample mass outside the sector we actually care about.

## What I would test next

Two follow-ups are worth doing before drawing a broader conclusion.

First, I would test whether this conclusion survives a larger routed grid over `n_spins = 8`, `J2/J1 = 0.0, 0.1, ..., 1.0`, shots `256, 512, 1024`, and depth `p = 1, 2, 3`.

Second, I would test a stricter sector-preservation strategy rather than spending more optimizer budget on the current setup. The current data show that execution-body deformation can dominate the source-level physics. A better next experiment is therefore a more explicitly sector-preserving ansatz or mixer, plus a utility rule that treats valid-sector reliability as a hard gate rather than a secondary metric.

That is the point of this repo at its best: it gives a defensible reason to stop paying for a quantum workflow when the evidence does not support it.
