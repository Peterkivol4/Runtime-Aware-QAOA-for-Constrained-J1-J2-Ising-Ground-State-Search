# Honest Limitations

This repository is an **execution-body deformation stack for frustrated-spin QAOA**, not a claim that shallow QAOA already solves hard J1-J2 instances better than classical methods.

## Current Limits

- The strongest conclusions still come from small exact-reference systems, where approximation ratio can saturate and hide the more informative feasibility story.
- The local-proxy and Aer paths are useful but do not substitute for a broad real-hardware study.
- Exact feasible bookkeeping grows exponentially with `n_spins`, so large-size statements must be framed as scaling-envelope observations rather than asymptotic claims.
- Mitigation can improve some operational metrics without improving the best feasible energy in a statistically meaningful way.
- A single lucky backend or noise profile should never be treated as the main result.

## What The Repo Is Good For

- testing whether execution-body conditions preserve enough physical trust to accept a QAOA result
- comparing BO, SPSA, and random-search tuning under matched primitive-call budgets
- exposing valid-sector collapse after routing, noise, finite shots, and mitigation
- producing reproducible artifact bundles for execution-body and frustration-axis controls

## What Still Requires Care

- interpreting flat BO vs SPSA deltas
- separating physically meaningful failure from implementation bugs
- deciding when `J2/J1 = 0.5` produces a real hardness signature versus a visually noisy one
- avoiding overstatement when the study grid is still compact
