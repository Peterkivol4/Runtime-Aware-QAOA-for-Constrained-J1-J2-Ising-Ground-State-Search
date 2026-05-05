# SpinMesh Runtime: A Dissent Memo on QAOA Under Execution-Body Deformation

**Claim.** Runtime is a physical deformation channel. This repo measures how much it deforms, and on current workloads the answer is: too much to trust QAOA over classical.

SpinMesh is intentionally not framed as a quantum-advantage demo. It is a refusal framework: hold the Hamiltonian, ansatz, angles, and seed fixed; send the circuit through routing, calibration age, finite shots, backend topology, queue delay, session drift, and mitigation; then ask whether the measured physics still deserves trust.

![Execution-body routing deformation curve](results/execution_body/routing_deformation_curve.png)

**Current verdict.** In the fixed-circuit execution-body sweep, the same source-level QAOA circuit produced different physical-observable errors after routing and noisy execution. Transpiled depth ranged from `378` to `1568`, two-qubit gate count ranged from `96` to `400`, and the compact trust gate rejected all `90` quantum execution records because the execution body had deformed the measured physics too strongly (`results/execution_body/routing_deformation_report.md`, `results/execution_body/runtime_decision_boundary.md`).

**Plain-English takeaway.** The negative result is the point. If a quantum workflow cannot preserve the physical sector, correlations, and decision stability after execution, then low-energy samples are not enough. The classical result is not just cheaper here; it is more trustworthy.

If you want the running process and not just the conclusion, read [RESEARCH_JOURNAL.md](RESEARCH_JOURNAL.md).

I built this after [LayerField QAOA](https://github.com/Peterkivol4/portfolio-qaoa-characterization) made me suspicious of clean depth stories and before [FieldLine VQE](https://github.com/Peterkivol4/Tfim-vqe-symmetry-bench) and [TeleportDim](https://github.com/Peterkivol4/Teleportdim-hardware-study) because I wanted to isolate one uncomfortable question first: what if the execution environment itself is changing the physics more than the source-level circuit does?

This repository studies **execution-body deformation** in QAOA for constrained random-bond **J1-J2 Ising** systems. Instead of treating runtime as bookkeeping, SpinMesh asks whether the physical conclusion remains stable after a fixed source-level circuit passes through routing, calibration drift, finite shots, backend topology, session policy, and measurement correction.

`spinmesh_runtime` is the supported public package surface; `ionmesh_runtime` remains only for internal compatibility and backward support.

## What this repo argues

- QAOA can be evaluated as an executed physical experiment, not only as an abstract ansatz.
- The same Hamiltonian and ansatz are not the same experiment after routing, finite shots, drift, and mitigation.
- Valid-sector leakage is not cosmetic noise; it is evidence that the measured state has left the physical sector being studied.
- The current evidence is classical-first because the trust gate rejects the compact quantum records while exact fixed-sector baselines remain stable.
- The repo's value is decision-quality, not advantage-claiming: it tells you when to stop paying for a quantum result.

For the concrete dissent memo, see [docs/why_i_dont_trust_this_result.md](docs/why_i_dont_trust_this_result.md).

## What this project is

- a study of whether execution conditions change physical conclusions in QAOA experiments
- a provenance layer for routing, calibration, shot, session, mitigation, and backend effects
- a trust-gated decision framework that can reject quantum results when the execution body has deformed the physics too much

## What this project is not

- not a quantum advantage claim
- not only an optimizer benchmark
- not only runtime accounting

See [docs/execution_body_deformation.md](docs/execution_body_deformation.md) for the full framing and experiment roadmap.

## One-command reproducibility

Run these from an activated virtual environment:

```bash
python -m pip install -e ".[dev,quantum,runtime]"
python -m spinmesh_runtime.cli --mode single --runtime-mode local_proxy --n-spins 6 --magnetization-m 0 --lattice-type j1j2_frustrated --j1-coupling 1.0 --j2-coupling 0.5 --depth 2 --fourier-modes 2
PYTHONPATH=src python tools/run_execution_body_experiments.py --output-dir results/execution_body
pytest
```

## The Dissent

The compact execution-body study in `results/execution_body/` fixes the Hamiltonian, optimized angles, seed family, and QAOA depth, then varies routing, topology, layout, calibration age, shot body, session policy, and mitigation. The source experiment stays fixed. The execution body changes.

That should be enough to make the result uncomfortable: two-qubit gate count correlates with correlation error at `r ~= 0.60`, routed Aer collapse leaves only about one third of samples in the valid magnetization sector near `J2/J1 = 0.5`, and one mitigation case improves the energy number while worsening correlation error. SpinMesh treats that as a failed physical measurement, not a near miss.

The practical message is blunt: QAOA can still be studied, but these outputs should not be trusted over the fixed-sector classical reference on the current workloads.

## Frustration-axis valid-ratio sweep

The fine `J2/J1` sweep in `results/frustration_axis/` fixes `n_spins = 8`, `p = 2`, and `256` shots while sweeping `J2/J1 = 0.0, 0.1, ..., 1.0`. Under the clean local-proxy Dicke/XY path, valid-sector ratio declines as frustration is increased but does **not** collapse below `0.5`; at `J2/J1 = 0.5`, the all-method mean is `0.8783`.

The routed Aer control in `results/frustration_axis_aer/` fixes a six-spin routed execution body and does reproduce collapse, but it is broad rather than sharply localized: the mean valid-sector ratio at `J2/J1 = 0.5` is `0.3166`, while the endpoint mean is `0.3154`.

This refines the headline: valid-ratio collapse is currently better explained as an execution-body deformation effect than as a sharp intrinsic dip exactly at the `J2/J1 = 0.5` point.

## Research question

> For a fixed frustrated-spin QAOA problem, when do runtime conditions change the physical conclusion of the experiment: energy ranking, magnetization, correlations, phase identification, or quantum-vs-classical decision, even if the source-level circuit and optimizer are unchanged?

## Main contribution

The main contribution of this repo is not a claim of quantum advantage. It is a **reproducible execution-body framework** that combines:

- a problem layer for constrained frustrated-spin instances
- a runtime-aware execution contract across `local_proxy`, `aer`, and IBM Runtime paths
- an `ExecutionDeformationVector` record for routing, calibration, shot, session, mitigation, and observable deformation
- a `RuntimeTrustGate` that accepts, warns, or rejects quantum results using canonical physical trust reasons
- a decision / utility-frontier layer that converts benchmark outputs into an execution recommendation
- a study pipeline that compares classical baselines, QAOA variants, mitigation bundles, and backend choices under matched operational constraints

On small systems, the framework is honest about negative or flat results. Classical baselines are not only faster here; they are often more physically stable under the measured execution conditions.

## Physics model

We study Ising spins `sigma_i in {-1, +1}` with fixed magnetization:

```text
E(sigma) = -sum_{i<j} J_ij sigma_i sigma_j - sum_i h_i sigma_i
subject to sum_i sigma_i = M
```

Using `sigma_i = 2 x_i - 1`, the problem maps onto the existing constrained binary QUBO stack with:

- binary variables `x_i in {0,1}`
- cardinality constraint `sum_i x_i = k = (M + N) / 2`
- quadratic objective `x^T Q x + constant`

That lets the repo reuse the optimizer, runtime, tracking, checkpoint, and decision infrastructure with minimal structural change.

## Supported lattice families

- `random_bond`
- `afm_uniform`
- `j1j2_frustrated`
- `diluted`
- `random_ferrimagnet`

The main study axis is the **frustration ratio** `J2 / J1`, with `J2 / J1 ~= 0.5` treated as the maximally frustrated point.

## Benchmark questions

The study pipeline is organized around three explicit questions:

1. Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency for frustrated ground-state search?
2. Does readout mitigation plus ZNE materially improve ground-state quality near the frustrated point?
3. How does valid-ratio collapse scale with system size, depth, and frustration ratio?

## Architecture

- **Problem layer**: lattice generation, QUBO conversion, exact feasible optimum, frustration metrics, remap vs penalty handling
- **Baselines**: exact search, greedy, local search, simulated annealing, random feasible search, classical BO surrogate
- **Quantum layer**: proxy, Aer, and Runtime V2 runners with Dicke-state initialization for the constrained sector
- **Optimization layer**: Fourier/direct parameterizations, BO/SPSA/random tuning, penalty epochs, checkpoint/resume
- **Tracking and reporting**: JSON/CSV/SQLite, findings reports, trust reports, utility frontiers, executive summaries
- **Decision layer**: cost-aware execution recommendation under matched runtime budgets
- **Validation layer**: live certification, calibration snapshotting, live-vs-Aer validation helpers

## Key instance metadata

Each benchmark instance records:

- `lattice_type`
- `n_spins`
- `magnetization_m`
- `j1_coupling`
- `j2_coupling`
- `j2_ratio`
- `disorder_strength`
- `frustration_index`
- `energy_gap_to_second_lowest` when available

## Output artifacts

A study sweep writes:

- `*_results.json`
- `*_summary.csv`
- `*.sqlite`
- `*_aggregates.csv`
- `*_performance_profile.csv`
- `*_findings.json`
- `*_findings.md`
- `*_findings.tex`
- plots:
  - `*_approx_gap.png`
  - `*_sample_efficiency.png`
  - `*_success_vs_noise.png`
  - `*_valid_ratio_vs_depth.png`
  - `*_valid_sector_ratio_vs_spins.png`
  - `*_energy_gap_vs_j2_ratio.png`
  - `*_mitigation_vs_shots.png`
  - `*_performance_profile.png`

Execution-body studies write records, trust reports, and plots under `results/execution_body/`; see [results/execution_body/README.md](results/execution_body/README.md). The current compact execution-body sweep contains `90` records and shows that the same fixed source circuit changes observable error as transpiled depth and two-qubit count inflate.

## Detailed install options

Base install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

With Aer:

```bash
pip install -e ".[quantum]"
```

With IBM Runtime support:

```bash
pip install -e ".[quantum,runtime]"
```

With developer extras:

```bash
pip install -e ".[dev,quantum,runtime]"
```

## More CLI examples

Smoke test:

```bash
python -m spinmesh_runtime.cli --mode smoke --runtime-mode local_proxy
```

Single benchmark on a frustrated six-spin instance:

```bash
python -m spinmesh_runtime.cli \
  --mode single \
  --runtime-mode aer \
  --n-spins 6 \
  --magnetization-m 0 \
  --lattice-type j1j2_frustrated \
  --j1-coupling 1.0 \
  --j2-coupling 0.5 \
  --depth 2 \
  --fourier-modes 2
```

Study sweep over size, frustration ratio, and disorder:

```bash
python -m spinmesh_runtime.cli \
  --mode study \
  --runtime-mode local_proxy \
  --study-num-seeds 4 \
  --study-n-spins 4,6,8 \
  --study-j2-ratios 0.0,0.25,0.5,0.75,1.0 \
  --study-disorder-levels 0.0,0.1,0.3 \
  --study-depths 1,2,3 \
  --study-shot-budgets 64,128,256 \
  --output-prefix results/ising_study/ising_runtime_qaoa
```

Execution-body deformation study:

```bash
PYTHONPATH=src python tools/run_execution_body_experiments.py --output-dir results/execution_body
```

Frustration-axis valid-sector sweep:

```bash
PYTHONPATH=src python tools/run_frustration_axis_sweep.py --output-dir results/frustration_axis
```

Live validation harness:

```bash
python tools/run_live_validation.py --runtime-backend ibm_fez --live-repeats 2 --aer-repeats 2
```

Runtime trust report from execution-deformation records:

```bash
python -m spinmesh_runtime.cli \
  --mode runtime_trust_report \
  --execution-body-input results/execution_body/execution_deformation_records.csv \
  --trust-policy configs/runtime_trust_gate.yaml \
  --runtime-trust-output results/execution_body/runtime_decision_boundary.md
```

## Project structure

```text
src/spinmesh_runtime/        active public package path
tests/                       regression and benchmark tests
tools/                       study, validation, and release helpers
docs/                        architecture and reporting notes
configs/                     trust-gate and run-policy examples
```

## Notes

- Historical compatibility shims exist for older scripts, but the active user-facing semantics are Ising-native: `n_spins`, `magnetization_m`, `lattice_type`, and `J2/J1`.
- The exact-state bookkeeping remains exponential in `n_spins`, so large-scale claims should be interpreted carefully.
