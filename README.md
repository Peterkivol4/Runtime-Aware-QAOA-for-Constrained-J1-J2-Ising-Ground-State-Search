# Runtime-Aware QAOA for Constrained J1-J2 Ising Ground-State Search

This repository benchmarks **runtime-aware QAOA** on the constrained random-bond **J1-J2 Ising model** on square-lattice geometries under realistic NISQ execution constraints: limited shots, routing overhead, mitigation costs, session management, and backend variability.

The active package surface is `spinmesh_runtime`; historical import shims remain only for backward compatibility.

## Research question

> Under realistic shot, routing, mitigation, and session-management constraints, when does runtime-aware QAOA improve constrained J1-J2 Ising ground-state approximation quality over strong classical baselines and lower-cost QAOA tuning strategies?

## Main contribution

The main contribution of this repo is not a claim of quantum advantage. It is a **reproducible benchmarking framework** that combines:

- a problem layer for constrained frustrated-spin instances
- a runtime-aware execution contract across `local_proxy`, `aer`, and IBM Runtime paths
- a decision / utility-frontier layer that converts benchmark outputs into an execution recommendation
- a study pipeline that compares classical baselines, QAOA variants, mitigation bundles, and backend choices under matched operational constraints

On small systems, the framework is honest about negative or flat results. That is a feature, not a bug.

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
- **Tracking and reporting**: JSON/CSV/SQLite, findings reports, performance profiles, utility frontiers, executive summaries
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

## Install

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

## CLI examples

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

Pilot study:

```bash
python tools/run_pilot_study.py
```

Paper-style local study:

```bash
python tools/run_paper_study.py --profile full --label submission_full --output-dir results/paper_full
```

Live validation harness:

```bash
python tools/run_live_validation.py --runtime-backend ibm_fez --live-repeats 2 --aer-repeats 2
```

## Project structure

```text
src/spinmesh_runtime/        active public package path
src/ionmesh_runtime/         implementation package
tests/                       regression and benchmark tests
tools/                       study, validation, and release helpers
docs/                        architecture and reporting notes
```

## Notes

- Historical compatibility shims exist for older scripts, but the active user-facing semantics are Ising-native: `n_spins`, `magnetization_m`, `lattice_type`, and `J2/J1`.
- The exact-state bookkeeping remains exponential in `n_spins`, so large-scale claims should be interpreted carefully.
