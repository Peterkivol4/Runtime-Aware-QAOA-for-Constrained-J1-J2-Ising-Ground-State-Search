# Session Drift Report

This compact run compares batched execution against split and drifted execution. Each row aggregates equivalent circuit executions under a different session policy.

| session_policy | session_duration_seconds | noise_scale | energy_error_vs_ideal_qaoa | magnetization_error | correlation_error | observed_phase_label |
| --- | --- | --- | --- | --- | --- | --- |
| single_session | 900 | 1 | 2.51243 | 0.0246582 | 0.391355 | invalid_sector_dominated |
| split_session | 900 | 1.3 | 2.5305 | 0.0322266 | 0.393099 | invalid_sector_dominated |
| randomized_order | 900 | 1.3 | 2.56444 | 0.0335286 | 0.394843 | invalid_sector_dominated |
| grouped_by_observable | 900 | 1.3 | 2.55565 | 0.0287272 | 0.396447 | invalid_sector_dominated |
