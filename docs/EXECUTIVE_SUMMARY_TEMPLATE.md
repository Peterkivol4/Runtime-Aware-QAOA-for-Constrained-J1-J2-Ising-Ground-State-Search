# Executive Summary Template

Use this template when turning a benchmark bundle into a short reviewer-facing summary.

## Problem

This study benchmarks runtime-aware QAOA on the constrained random-bond J1-J2 Ising model with fixed magnetization. The main stress point is the frustration ratio `J2/J1`, especially near `0.5`.

## Questions

- Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency?
- Does mitigation improve ground-state quality enough to justify its shot overhead?
- How does valid-sector ratio change with system size, depth, and frustration?

## Main Result

State the conclusion plainly:

- whether QAOA beat the classical frontier or not
- whether the main result is positive, flat, or negative
- whether the `J2/J1 = 0.5` region behaved like a harder regime

## Operational Takeaway

- recommended method family
- expected runtime range
- expected shot cost
- whether mitigation is worth enabling on the tested grid

## One Honest Limitation

Name the main reason the result should be interpreted carefully:

- narrow grid
- small exact sizes
- backend sensitivity
- insufficient live-hardware evidence
