# Submission Draft Chapter

This file is now a **physics-first working draft placeholder** for the constrained J1-J2 Ising submission. The active written structure should follow [THESIS_CHAPTER_SCAFFOLD.md](./THESIS_CHAPTER_SCAFFOLD.md), and the active evidence layer should come from the spin-native study bundles produced after the repository pivot.

## Core Claim To Defend

Under realistic shot, mitigation, and backend constraints, runtime-aware QAOA can be benchmarked honestly on the fixed-magnetization J1-J2 Ising model, with explicit comparison against strong classical baselines and explicit visibility into valid-sector collapse.

## Mandatory Elements Before Submission

- direct tests of the Ising-to-QUBO mapping and magnetization-to-cardinality mapping
- a documented Dicke-state initialization in the main QAOA path
- benchmark figures for:
  - approximation gap vs `J2/J1`
  - valid-sector ratio vs system size and depth
  - BO vs SPSA sample efficiency
  - mitigation delta near `J2/J1 = 0.5`
- a related-work section that covers QAOA, constrained variational optimization, frustrated spin systems, and mitigation/runtime literature

## Status Note

Treat older finance-era chapter drafts as archived iteration history. They should not be used as the active thesis text for the current repository state.
