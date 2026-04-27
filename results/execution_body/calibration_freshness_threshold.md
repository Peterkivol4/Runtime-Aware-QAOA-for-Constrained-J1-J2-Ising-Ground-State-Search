# Calibration Freshness Threshold

This simulated calibration-age experiment holds the source circuit fixed and scales the execution noise with calibration age.

No additional phase-label change occurred after the freshest observed execution; routing/noise had already moved the observed label away from the ideal source label. Observable errors and trust-gate pressure still changed with age.

| calibration_age_seconds | noise_scale | energy_error_vs_ideal_qaoa | magnetization_error | correlation_error | confidence_interval_width | observed_phase_label |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 2.54881 | 0.0138346 | 0.397075 | 0.250777 | invalid_sector_dominated |
| 300 | 1.16667 | 2.56395 | 0.0128581 | 0.398889 | 0.252589 | invalid_sector_dominated |
| 900 | 1.5 | 2.50731 | 0.0519206 | 0.394703 | 0.238663 | invalid_sector_dominated |
| 1800 | 2 | 2.50535 | 0.0327148 | 0.390797 | 0.250071 | invalid_sector_dominated |
| 3600 | 3 | 2.58299 | 0.070638 | 0.40698 | 0.247735 | invalid_sector_dominated |
