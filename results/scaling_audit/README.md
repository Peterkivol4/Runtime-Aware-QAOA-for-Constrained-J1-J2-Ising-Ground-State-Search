# Scaling Audit Evidence

This directory records lightweight scaling-envelope checks for the current implementation.

## Recorded artifacts

- [scaling_audit_local_proxy_20260413.json](./scaling_audit_local_proxy_20260413.json)
- [scaling_audit_local_proxy_20260413.md](./scaling_audit_local_proxy_20260413.md)
- [scaling_audit_local_proxy_extension_20260413.json](./scaling_audit_local_proxy_extension_20260413.json)
- [scaling_audit_local_proxy_extension_20260413.md](./scaling_audit_local_proxy_extension_20260413.md)
- [scaling_audit_local_proxy_boundary_20_20260414.json](./scaling_audit_local_proxy_boundary_20_20260414.json)
- [scaling_audit_local_proxy_boundary_20_20260414.md](./scaling_audit_local_proxy_boundary_20_20260414.md)
- [scaling_audit_local_proxy_boundary_22_20260414.json](./scaling_audit_local_proxy_boundary_22_20260414.json)
- [scaling_audit_local_proxy_boundary_22_20260414.md](./scaling_audit_local_proxy_boundary_22_20260414.md)
- [scaling_audit_local_proxy_boundary_24_20260414_timeout.json](./scaling_audit_local_proxy_boundary_24_20260414_timeout.json)
- [scaling_audit_local_proxy_boundary_24_20260414_timeout.md](./scaling_audit_local_proxy_boundary_24_20260414_timeout.md)
- [scaling_audit_aer_20260413.json](./scaling_audit_aer_20260413.json)
- [scaling_audit_aer_20260413.md](./scaling_audit_aer_20260413.md)
- [scaling_audit_aer_extension_20260413.json](./scaling_audit_aer_extension_20260413.json)
- [scaling_audit_aer_extension_20260413.md](./scaling_audit_aer_extension_20260413.md)

## What this shows

- The smoke-test path completed through `n=18` on `local_proxy`.
- A boundary extension completed through `n=22` on `local_proxy`.
- The `n=24` local-proxy smoke probe exceeded a five-minute practical guard window and was manually stopped.
- The smoke-test path completed through `n=12` on `aer`.
- The code still carries exact-state-space bookkeeping, so these results show a tested envelope rather than asymptotic scalability.

## How to interpret it

- This is evidence that the implementation still runs at moderate larger sizes in a smoke-test setting.
- It is not evidence that the full study stack is cheap at large `n`.
- It is not evidence that live hardware is practical at those larger sizes under an IBM open plan.
