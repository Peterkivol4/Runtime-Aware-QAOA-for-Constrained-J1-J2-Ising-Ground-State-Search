# Submission Draft Chapter

This file is now a **physics-first working draft placeholder** for the constrained J1-J2 Ising submission. The active written structure should follow [THESIS_CHAPTER_SCAFFOLD.md](./THESIS_CHAPTER_SCAFFOLD.md), and the active evidence layer should come from the spin-native study bundles produced after the repository pivot.

## Core Claim To Defend

Under realistic routing, calibration, shot, mitigation, and backend constraints, QAOA can be benchmarked honestly on the fixed-magnetization J1-J2 Ising model, with explicit visibility into when the execution body deforms physical observables enough to reject the quantum result.

## Mandatory Elements Before Submission

- direct tests of the Ising-to-QUBO mapping and magnetization-to-cardinality mapping
- a documented Dicke-state initialization in the main QAOA path
- benchmark figures for:
  - routing deformation vs observable error
  - valid-sector ratio vs `J2/J1`
  - routed Aer collapse vs clean local-proxy sector preservation
  - mitigation shift vs observable instability
- a related-work section that covers QAOA, constrained variational optimization, frustrated spin systems, and mitigation/runtime literature

## Status Note

Treat older finance-era chapter drafts as archived iteration history. They should not be used as the active thesis text for the current repository state.
