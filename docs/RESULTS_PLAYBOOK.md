# Results Playbook

This repository is meant to produce a defensible evidence bundle for **constrained J1-J2 Ising ground-state search**, not just code that compiles.

## Quick Start

Generate the compact execution-body study:

```bash
PYTHONPATH=src python tools/run_execution_body_experiments.py --output-dir results/execution_body
```

Generate the clean frustration-axis valid-sector sweep:

```bash
PYTHONPATH=src python tools/run_frustration_axis_sweep.py --output-dir results/frustration_axis
```

Generate the routed Aer control:

```bash
PYTHONPATH=src python tools/run_frustration_axis_aer_sweep.py --output-dir results/frustration_axis_aer
```

## What A Good Bundle Should Answer

The active study layer should visibly answer three questions:

1. Does routing/topology/layout change measured physical observables when the source circuit is fixed?
2. Does finite-shot, calibration, session, or mitigation policy restore or further deform physical trust?
3. Does valid-sector ratio degrade intrinsically across `J2/J1`, or does collapse appear mainly after routed/noisy execution?

## Minimum Artifact Set

A current evidence bundle should contain:

- execution-body records: `results/execution_body/execution_deformation_records.csv`
- trust report: `results/execution_body/runtime_decision_boundary.md`
- routing report and plot: `results/execution_body/routing_deformation_report.md`, `routing_deformation_curve.png`
- frustration-axis records: `results/frustration_axis/frustration_axis_valid_ratio_records.csv`
- routed Aer control: `results/frustration_axis_aer/frustration_axis_aer_records.csv`
- figure artifacts for routing deformation, shot-body stability, mitigation deformation, and valid-sector ratio vs `J2/J1`

## Recommended Study Progression

1. Run the execution-body sweep and inspect whether routing inflation changes observable error.
2. Run the clean `J2/J1` sweep and check whether valid-sector loss is intrinsic to the frustration axis.
3. Run the routed Aer control and compare whether collapse appears only after execution-body deformation.
4. Use at least three seeds for any claim about reproducibility or flatness.
5. Treat live-hardware runs as appendices unless the hardware grid is large enough to stand on its own.

## What Not To Claim

- Do not claim quantum advantage from a single backend or a single seed.
- Do not claim scaling from exact-reference studies without naming the exact-system-size boundary.
- Do not claim mitigation helps unless it improves physical observables, not only the energy number.
