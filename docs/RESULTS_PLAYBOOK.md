# Results Playbook

This repository is meant to produce a defensible evidence bundle for **constrained J1-J2 Ising ground-state search**, not just code that compiles.

## Quick Start

Generate a small local-proxy pilot study:

```bash
python tools/run_pilot_study.py
```

Inspect the resolved configuration without launching the study:

```bash
python tools/run_pilot_study.py --dry-run
```

Generate a small Aer-backed pilot study:

```bash
python tools/run_pilot_study.py --runtime-mode aer --label aer_pilot --output-dir results/aer_pilot
```

Generate a larger submission-oriented bundle:

```bash
python tools/run_paper_study.py --profile draft
```

## What A Good Bundle Should Answer

The active study layer should visibly answer three questions:

1. Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency?
2. Does mitigation materially improve ground-state quality near `J2/J1 = 0.5`?
3. How does valid-sector ratio degrade with system size, depth, and frustration?

## Minimum Artifact Set

A benchmark bundle should contain:

- timestamped ledger artifacts: `*_results.json`, `*_summary.csv`, `*.sqlite`
- aggregate tables: `*_aggregates.csv`, `*_performance_profile.csv`, `*_utility_frontier.csv`
- findings and decision artifacts: `*_findings.{json,md,tex}`, `*_decision_report.{json,md}`, `*_executive_summary.md`
- figures:
  - `*_approx_gap.png`
  - `*_sample_efficiency.png`
  - `*_success_vs_noise.png`
  - `*_valid_ratio_vs_depth.png`
  - `*_valid_sector_ratio_vs_spins.png`
  - `*_energy_gap_vs_j2_ratio.png`
  - `*_mitigation_vs_shots.png`
  - `*_performance_profile.png`

## Recommended Study Progression

1. Run the local-proxy pilot and check that the artifact schema is clean.
2. Run the same compact grid on Aer and compare whether the sign of the conclusion changes.
3. Expand the `J2/J1` sweep to include `0.0, 0.25, 0.5, 0.75, 1.0`.
4. Use at least three seeds for any claim about reproducibility or flatness.
5. Add a broader shot tier such as `256` or `512` if you want the mitigation cost curve to be visible.
6. Treat live-hardware runs as appendices unless the hardware grid is large enough to stand on its own.

## What Not To Claim

- Do not claim quantum advantage from a single backend or a single seed.
- Do not claim scaling from exact-reference studies without naming the exact-system-size boundary.
- Do not claim mitigation helps unless the gain survives the extra shot cost and appears in more than one window.
