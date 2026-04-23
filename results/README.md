# Results

This directory is the home for generated benchmark artifacts.

For a reproducible local-proxy pilot run, use:

```bash
python tools/run_pilot_study.py
```

That command writes a small evidence bundle under `results/pilot/` and records the exact resolved configuration in a manifest JSON file.

The pilot run is intentionally lightweight so it can complete on a normal laptop. It is a starting point for producing evidence, not the final thesis-scale benchmark grid.
