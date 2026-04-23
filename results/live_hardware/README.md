# Live Hardware Evidence

This directory records the real-QPU evidence captured in this workspace on **April 13-14, 2026**.

## Recorded artifact

- [ibm_fez_smoke_backend_mode_20260413.json](./ibm_fez_smoke_backend_mode_20260413.json)
- [ibm_fez_validation_suite_budgeted_20260413.json](./ibm_fez_validation_suite_budgeted_20260413.json)
- [ibm_fez_validation_suite_budgeted_20260413.md](./ibm_fez_validation_suite_budgeted_20260413.md)
- [ibm_fez_validation_suite_budgeted_20260413_backend_snapshot.json](./ibm_fez_validation_suite_budgeted_20260413_backend_snapshot.json)
- [ibm_fez_sparse_n8_appendix_20260414.json](./ibm_fez_sparse_n8_appendix_20260414.json)
- [ibm_fez_sparse_n8_appendix_20260414.md](./ibm_fez_sparse_n8_appendix_20260414.md)
- [ibm_fez_sparse_n8_appendix_20260414_backend_snapshot.json](./ibm_fez_sparse_n8_appendix_20260414_backend_snapshot.json)

## What this shows

- IBM Runtime authentication and backend selection succeeded against a non-simulator backend.
- A live smoke workload completed on `ibm_fez` in `backend` execution mode.
- The repository's runtime path reached a real measurement result instead of failing before submission.
- A budgeted live validation suite completed with repeatability, Aer parity, and a four-cell appendix sweep.
- A second budgeted appendix extension completed on `ibm_fez` for a harder `sparse`, `n=8` configuration, broadening the live evidence beyond the original appendix slice.

## What this does not show

- It is not a full benchmark grid.
- It is not a session-mode certification, because the open plan rejected session execution for this account tier.
- It is not evidence that checkpointed resume has been validated across a live session boundary.
