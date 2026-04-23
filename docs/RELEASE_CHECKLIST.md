# Release Checklist

Before packaging a public release:

1. Run `python tools/release_check.py --repo .`
2. Confirm `tools/cleanup_release.py --dry-run` returns no junk after cleanup.
3. If IBM Runtime access is available, export a fresh calibration snapshot with `tools/export_runtime_calibration.py`.
4. Re-run one Aer validation and one Runtime-backed validation if credentials are available.
5. Package only source, tests, tools, docs, and top-level project metadata.
