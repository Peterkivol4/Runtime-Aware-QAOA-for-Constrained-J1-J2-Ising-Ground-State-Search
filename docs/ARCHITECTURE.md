# Architecture

This repository is organized around five layers:

1. **Problem layer** in `problem.py` builds constrained J1-J2 Ising instances, converts them to QUBO form, and computes exact fixed-sector references on small systems.
2. **Baseline layer** in `baselines.py` provides exact search, local-field greedy, local search, simulated annealing, random feasible search, and classical surrogate search.
3. **Quantum execution layer** in `quantum.py` and `runtime_support.py` prepares fixed-magnetization initial states, separates optimization-time objective evaluation from final readout, and supports proxy, Aer, and Runtime V2 backends.
4. **Optimization layer** in `optimization.py` and `pipeline.py` handles Fourier/direct parameterizations, BO/SPSA/random tuning, penalty schedules, checkpointing, and shot-governor behavior.
5. **Tracking and reporting layer** in `tracking.py`, `plotting.py`, and `decision.py` writes JSON/CSV/SQLite artifacts, findings reports, performance profiles, utility frontiers, and execution recommendations.

## Runtime boundary

The stack is runtime-aware and recovery-aware, but live-hardware claims should only be made when the Runtime session, queueing, checkpoint, and readout paths have been exercised on a real backend.

## Compatibility boundary

The code still carries a few compatibility wrappers from the older package layout so historical scripts continue to import, but the active benchmark semantics are physics-native:

- `n_spins` is the system size
- `magnetization_m` selects the fixed sector
- `lattice_type` selects the coupling family
- `j2_ratio = j2_coupling / j1_coupling` is the primary hardness axis
