# Runtime-Aware QAOA Executive Summary

## Core questions
- Does BO-tuned Fourier QAOA outperform SPSA-tuned QAOA in sample efficiency?
- When does mitigation materially improve feasible-energy quality?
- How does valid-ratio collapse as asset count, depth, and noise increase?

## Recommended deployment stance
- recommendation: **run_classical**
- recommended method: **exact_feasible**
- expected approximation ratio: **1.0**
- expected valid ratio: **1.0**

## Key takeaways
- Matched-call sample efficiency favors bo_fourier.
- Mitigation helps most in a narrow window at n=4, depth=1, noise=0.000, shots=64.
- Valid-ratio collapse (<0.5) appears in 100.0% of aggregated QAOA windows.
- Best Dolan-Moré profile area: bo_direct.

## Honest limitation
- This package is runtime-aware and recovery-aware, but should not be labeled live IBM hardware certified until the session-recovery harness is exercised on a real backend.
