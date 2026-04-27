# Executive Summary Template

Use this template when turning a benchmark bundle into a short reviewer-facing summary.

## Problem

This study benchmarks execution-body deformation in QAOA on the constrained random-bond J1-J2 Ising model with fixed magnetization. The main question is whether routing, calibration, finite shots, session policy, and mitigation change the measured physics after the source circuit is fixed.

## Questions

- Does routing/topology/layout change the measured energy, magnetization, or correlations?
- Does mitigation improve physical observables, or only the energy number?
- Does valid-sector ratio collapse intrinsically across `J2/J1`, or mainly after routed/noisy execution?

## Main Result

State the conclusion plainly:

- whether the trust gate accepted or rejected the quantum execution
- whether the main result is positive, flat, or negative
- whether the `J2/J1 = 0.5` region behaved differently from the execution-body collapse baseline

## Operational Takeaway

- accepted, warned, or rejected quantum result
- dominant rejection reason
- observed routing/depth/two-qubit burden
- whether mitigation is worth enabling on the tested execution body

## One Honest Limitation

Name the main reason the result should be interpreted carefully:

- narrow grid
- small exact sizes
- backend sensitivity
- insufficient live-hardware evidence
