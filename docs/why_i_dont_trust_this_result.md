# Why I Do Not Trust This QAOA Result

This note is deliberately a dissent memo. The useful result in this repository is not that QAOA wins. It is that the execution stack can deform the measured physics enough that I should refuse the quantum answer.

## Workload

The case comes from the current execution-body and routed Aer controls in `results/execution_body/` and `results/frustration_axis_aer/`.

- lattice: `j1j2_frustrated`
- size: `n_spins = 6`
- magnetization sector: half filling (`M = 0`, so `k = 3`)
- frustration ratio: `J2/J1 = 0.5`
- disorder strength: `0.0`
- execution body: routed Aer-style backend with `forked_heavy_hex` topology and `sabre` routing

This is exactly the kind of small, maximally frustrated workload where a shallow, symmetry-matched QAOA run is tempting. That is why the negative result matters.

## Budget and Setup

The quantum run was operationally plausible rather than absurdly expensive:

- backend path: routed `AerSimulator`
- QAOA depth: `p = 2`
- shot budget: `2048`
- topology: `forked_heavy_hex`
- routing method: `sabre`
- transpiler optimization level: `1`

The baseline reference on the same workload was `exact_feasible`.

## What I Expected

I did not expect a quantum-advantage result. The bar was lower and more practical: with Dicke-state initialization, a fixed-magnetization sector, and a six-spin frustrated instance, QAOA should at least preserve enough valid-sector probability mass and observable stability to justify trying it before defaulting to the classical fixed-sector reference.

That did not happen.

## What Failed

The clean local-proxy path did not intrinsically collapse at the frustration point: the fine sweep reports a mean valid-sector ratio of `0.8783` at `J2/J1 = 0.5`. The routed Aer control is the warning sign. At the same nominal frustration point, the routed execution body reports:

- `mean_valid_ratio = 0.3166`
- `collapse_fraction = 1.0`
- `mean_correlation_error = 0.4006`
- `mean_routing_inflation = 33.5926`
- `mean_two_qubit_gate_count = 196`

Only about one third of the measured probability mass stayed in the physical magnetization sector. That is not a cosmetic measurement problem; it means the execution body changed the experiment I thought I was running.

The broader fixed-circuit execution-body sweep gives the same reason for distrust:

- `90 / 90` quantum records were rejected by the compact trust gate
- transpiled depth ranged from `378` to `1568`
- two-qubit gate count ranged from `96` to `400`
- two-qubit gate count correlated with correlation error at approximately `r = 0.60`

Mitigation did not rescue the case. One ZNE-style correction improved the energy error while worsening the correlation error. I do not trust a mitigation policy that makes the headline scalar look better while making the physical observable worse.

## Why The Classical Recommendation Survived

The same compact workload has an exact fixed-sector classical reference:

- exact feasible energy: `-5.00000000`
- exact feasible bitstring: `101010`
- valid-sector ratio: `1.0`
- shots: `0`

This is the point of the trust gate. If I looked only at energy, I could talk myself into treating the QAOA run as promising. SpinMesh blocks that story. It asks whether the quantum output preserved the sector, observables, and decision stability after routing, finite shots, and mitigation.

For this workload, the answer is no. QAOA bought routed two-qubit depth, finite-shot uncertainty, valid-sector leakage, and mitigation ambiguity. The classical result stayed inside the sector by construction and gave the exact reference with no sampling cost.

## What I Would Test Next

First, I would run a larger routed grid over `n_spins = 8`, `J2/J1 = 0.0, 0.1, ..., 1.0`, shots `256, 512, 1024`, and depths `p = 1, 2, 3` to test whether the distrust boundary moves with size and depth.

Second, I would stop spending optimizer budget on the current ansatz until the sector-preservation problem is addressed. The next useful experiment is a stricter sector-preserving mixer or ansatz plus a hard trust rule that rejects any run whose valid-sector reliability collapses before energy is interpreted.

That is the repo's stance: runtime is not metadata, and a deformed quantum result does not deserve trust just because it came from a QAOA circuit.
