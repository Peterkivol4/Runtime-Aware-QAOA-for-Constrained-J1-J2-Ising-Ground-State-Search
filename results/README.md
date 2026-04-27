# Results

This directory contains the evidence bundles that support the current SpinMesh Runtime framing.

- `execution_body/` records execution-body deformation for a fixed QAOA source circuit.
- `frustration_axis/` records the clean local-proxy valid-sector sweep over `J2/J1 = 0.0, 0.1, ..., 1.0`.
- `frustration_axis_aer/` records the routed Aer control for the same frustration-axis question.
- `live_hardware/` contains hardware appendix material and calibration snapshots.

Regenerate the core execution-body bundle with:

```bash
PYTHONPATH=src python tools/run_execution_body_experiments.py --output-dir results/execution_body
```

Regenerate the frustration-axis controls with:

```bash
PYTHONPATH=src python tools/run_frustration_axis_sweep.py --output-dir results/frustration_axis
PYTHONPATH=src python tools/run_frustration_axis_aer_sweep.py --output-dir results/frustration_axis_aer
```
