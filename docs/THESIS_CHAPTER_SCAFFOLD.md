# Thesis Chapter Scaffold

## 1. Introduction

- frustrated magnetism and the J1-J2 Ising model as a benchmark family
- why fixed magnetization is a physically meaningful constrained sector
- why runtime-aware benchmarking matters for NISQ claims

## 2. Related Work

- QAOA and constrained variational optimization
- frustration and random-bond Ising benchmarking
- mitigation and runtime-cost studies
- classical baselines for small exact-reference spin systems

## 3. Problem Formulation

- define the Ising Hamiltonian
- define the magnetization-sector constraint
- show the spin-to-QUBO substitution `sigma_i = 2x_i - 1`
- explain the mapping from `M` to `k = (M + N)/2`

## 4. Method

- instance generation across `lattice_type`, `J2/J1`, disorder, and `n_spins`
- Dicke-state initialization and constrained QAOA ansatz
- BO, SPSA, and random-search parameter tuning
- classical baselines: exact, local-field greedy, local search, simulated annealing, random feasible search, classical BO surrogate
- runtime-aware accounting: shots, primitive calls, mitigation, checkpointing, and backend mode

## 5. Experimental Design

- study grid
- seed count
- backends: `local_proxy`, `aer`, and any live-runtime appendix
- metrics:
  - approximation gap
  - approximation ratio
  - valid-sector ratio
  - `P_succ`
  - runtime seconds
  - primitive-call count
  - total shots

## 6. Results

- BO vs SPSA sample efficiency
- mitigation effect near `J2/J1 = 0.5`
- valid-sector collapse versus size, depth, and frustration
- backend and noise sensitivity

## 7. Discussion

- what the `J2/J1 = 0.5` landscape says about hardness
- whether Dicke initialization helps sector fidelity
- why flat deltas can still be scientifically meaningful
- where the classical frontier still dominates

## 8. Limitations And Future Work

- exact-size boundary
- broader shot tiers and deeper circuits
- broader disorder sweep
- more live-hardware cells
