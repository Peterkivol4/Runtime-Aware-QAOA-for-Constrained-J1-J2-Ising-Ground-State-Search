# Why Classical Still Wins on One Concrete J1-J2 Workload

This note exists for one reason: the most useful outcome of a runtime-aware benchmark is often a decision not to spend more quantum budget.

## Workload

The case below comes from the saved Aer pivot sweep in `results/pivot_validation/compact_j2_sweep_aer_aggregates.csv`.

- lattice: `j1j2_frustrated`
- size: `n_spins = 6`
- magnetization sector: half-filling (`M = 0`, so `k = 3`)
- frustration ratio: `J2/J1 = 0.5`
- disorder strength: `0.0`
- noise level: `0.04`

This is a clean, small, maximally frustrated test case. It is exactly the sort of workload where a shallow, symmetry-matched QAOA pass is tempting.

## Budget and setup

The concrete comparison that mattered most was the lowest-budget QAOA slice that still looked operationally plausible:

- backend path: `aer`
- QAOA depth: `p = 1`
- shot budget: `64`
- optimizer: `bo_direct`
- mitigation: `none`, then `readout`

The baseline reference on the same workload was `exact_feasible`.

## What we expected

The expectation was modest, not grandiose. With Dicke-state initialization, a fixed-magnetization sector, and a small six-spin instance, a low-budget QAOA run could plausibly have been worth trying even if it did not beat the classical optimum outright.

The bar was therefore not "prove quantum advantage." The bar was "preserve enough valid-sector mass, at low enough operational cost, that a quantum-first recommendation is defensible."

## What failed

The energy metric alone looked deceptively fine. For the `bo_direct` run above, the saved aggregate row reports:

- `mean_ratio = 1.0`
- `mean_valid_ratio = 0.3307291666666667`
- `p_succ = 0.033854166666666664`
- `mean_total_shots = 960`
- `mean_objective_calls = 3`
- `mean_runtime_seconds = 0.5220749378204346`

In other words, the run could still recover exact-feasible energy on the shots that landed in the right sector, but only about one third of measured mass stayed in the valid magnetization sector and the feasible-success probability was about `3.39%`.

Readout mitigation did not rescue this case:

- `mean_valid_ratio` moved only from `0.3307291666666667` to `0.33111343443016406`
- `p_succ` moved slightly in the wrong direction, from `0.033854166666666664` to `0.03299271528018215`

Changing the optimizer did not fix the problem either. On the same workload slice:

- `bo_fourier` also stayed at `mean_valid_ratio = 0.3307291666666667`
- `spsa_fourier` used `2496` shots and `9` objective calls but only reached `mean_valid_ratio = 0.33072916666666663`

Even the best QAOA variant in this exact workload family under the same noise level, `random_fourier` with `readout+zne`, only reached:

- `mean_valid_ratio = 0.4103221615839281`
- `p_succ = 0.030997271803104954`
- `mean_total_shots = 1376`

That is still not enough to justify a quantum-first recommendation.

## Why the classical recommendation survived

The same saved aggregate file reports, for `exact_feasible` on the identical workload:

- `mean_ratio = 1.0`
- `p_succ = 1.0`
- `mean_valid_ratio = 1.0`
- `mean_total_shots = 0`
- `mean_objective_calls = 0`
- `mean_runtime_seconds = 0.0`

This is the concrete reason the decision layer remains useful. If we looked only at approximation ratio, the shallow QAOA runs would appear much better than they really are. The framework prevents that mistake by charging QAOA for the thing that matters operationally: how much valid, decision-usable probability mass survives after routing, noise, and finite-shot execution.

For this workload, the classical recommendation survived because QAOA bought no decision-quality gain. It bought extra shots, extra calls, and extra runtime while still leaving most of the sample mass outside the sector we actually care about.

## What I would test next

Two follow-ups are worth doing before drawing a broader conclusion.

First, I would test whether the clean maximally frustrated slice is specifically the problem, or whether the issue is the current shallow execution contract. In the same Aer pivot study, some `J2/J1 = 0.5` cases with `disorder_strength = 0.3` retain much higher valid ratios, so the next question is whether disorder is genuinely making the sector easier to preserve or merely changing where the post-selection burden shows up.

Second, I would test a stricter sector-preservation strategy rather than spending more optimizer budget on the current setup. The current data show that extra optimization steps and light mitigation do not repair the main failure mode. A better next experiment is therefore a more explicitly sector-preserving ansatz or mixer, plus a utility rule that treats valid-sector reliability as a hard gate rather than a secondary metric.

That is the point of this repo at its best: it gives a defensible reason to stop paying for a quantum workflow when the evidence does not support it.
