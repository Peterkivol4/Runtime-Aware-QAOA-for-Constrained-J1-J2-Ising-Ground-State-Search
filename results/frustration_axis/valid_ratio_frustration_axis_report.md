# Valid-Ratio Collapse Across the Frustration Axis

## Fixed sweep design

- `n_spins`: `8`
- `magnetization_m`: `0`
- QAOA depth: `p = 2`
- final readout shots per method/seed/ratio: `256`
- optimizer iterations per method: `6`
- seeds: `810` through `814`
- `J2/J1` ratios: `0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0`
- methods: `bo_fourier, spsa_fourier, random_fourier, bo_direct`
- noise level: `0.04`
- disorder strength: `0.3`
- elapsed wall-clock seconds: `12.89`

The shot governor is disabled for this sweep, so the final-readout shot budget is fixed across the whole frustration axis.

## Main interpretation

The fine sweep shows lower valid ratio at `J2/J1 = 0.5` than at the endpoints, but not a clean local dip relative to the adjacent shoulders.

- center mean valid ratio: `0.87832`
- endpoint mean valid ratio: `0.895312`
- adjacent-shoulder mean valid ratio (`0.4`, `0.6`): `0.857715`
- center minus endpoints: `-0.0169922`
- center minus shoulders: `0.0206055`

## All-method valid-ratio aggregate

| j2_ratio | n | mean_valid_ratio | ci95_valid_ratio | collapse_fraction | mean_approximation_gap | mean_frustration_index |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 20 | 0.97168 | 0.0055231 | 0 | 0 | 0 |
| 0.1 | 20 | 0.970508 | 0.00537016 | 0 | 0 | 1 |
| 0.2 | 20 | 0.969336 | 0.00660195 | 0 | 0 | 1 |
| 0.3 | 20 | 0.961719 | 0.00581493 | 0 | 0 | 1 |
| 0.4 | 20 | 0.942383 | 0.00863843 | 0 | 0 | 1 |
| 0.5 | 20 | 0.87832 | 0.0236717 | 0 | 0 | 1 |
| 0.6 | 20 | 0.773047 | 0.0447947 | 0 | 0 | 1 |
| 0.7 | 20 | 0.719922 | 0.0471607 | 0 | 0 | 1 |
| 0.8 | 20 | 0.742188 | 0.0401343 | 0 | 0 | 1 |
| 0.9 | 20 | 0.776367 | 0.036295 | 0 | 0 | 1 |
| 1 | 20 | 0.818945 | 0.0311012 | 0 | 0 | 1 |

## Method-level aggregate

| method | j2_ratio | n | mean_valid_ratio | ci95_valid_ratio | collapse_fraction | mean_approximation_gap |
| --- | --- | --- | --- | --- | --- | --- |
| bo_direct | 0 | 5 | 0.971094 | 0.0115099 | 0 | 0 |
| bo_direct | 0.1 | 5 | 0.964063 | 0.0139923 | 0 | 0 |
| bo_direct | 0.2 | 5 | 0.960938 | 0.0116113 | 0 | 0 |
| bo_direct | 0.3 | 5 | 0.953125 | 0.00998253 | 0 | 0 |
| bo_direct | 0.4 | 5 | 0.942969 | 0.0190023 | 0 | 0 |
| bo_direct | 0.5 | 5 | 0.882031 | 0.047899 | 0 | 0 |
| bo_direct | 0.6 | 5 | 0.789062 | 0.0891879 | 0 | 0 |
| bo_direct | 0.7 | 5 | 0.695312 | 0.125735 | 0 | 0 |
| bo_direct | 0.8 | 5 | 0.723437 | 0.0998077 | 0 | 0 |
| bo_direct | 0.9 | 5 | 0.757031 | 0.0860571 | 0 | 0 |
| bo_direct | 1 | 5 | 0.819531 | 0.0859207 | 0 | 0 |
| bo_fourier | 0 | 5 | 0.976562 | 0.00937695 | 0 | 0 |
| bo_fourier | 0.1 | 5 | 0.964844 | 0.0121056 | 0 | 0 |
| bo_fourier | 0.2 | 5 | 0.966406 | 0.0146473 | 0 | 0 |
| bo_fourier | 0.3 | 5 | 0.965625 | 0.0103854 | 0 | 0 |
| bo_fourier | 0.4 | 5 | 0.946094 | 0.0189714 | 0 | 0 |
| bo_fourier | 0.5 | 5 | 0.875781 | 0.0592259 | 0 | 0 |
| bo_fourier | 0.6 | 5 | 0.773438 | 0.0967539 | 0 | 0 |
| bo_fourier | 0.7 | 5 | 0.723437 | 0.0685395 | 0 | 0 |
| bo_fourier | 0.8 | 5 | 0.738281 | 0.0710424 | 0 | 0 |
| bo_fourier | 0.9 | 5 | 0.798438 | 0.0595812 | 0 | 0 |
| bo_fourier | 1 | 5 | 0.815625 | 0.0461539 | 0 | 0 |
| random_fourier | 0 | 5 | 0.963281 | 0.0138237 | 0 | 0 |
| random_fourier | 0.1 | 5 | 0.975781 | 0.00658616 | 0 | 0 |
| random_fourier | 0.2 | 5 | 0.972656 | 0.0149248 | 0 | 0 |
| random_fourier | 0.3 | 5 | 0.960938 | 0.0145267 | 0 | 0 |
| random_fourier | 0.4 | 5 | 0.938281 | 0.0248563 | 0 | 0 |
| random_fourier | 0.5 | 5 | 0.866406 | 0.0526781 | 0 | 0 |
| random_fourier | 0.6 | 5 | 0.764844 | 0.0977904 | 0 | 0 |
| random_fourier | 0.7 | 5 | 0.719531 | 0.0981196 | 0 | 0 |
| random_fourier | 0.8 | 5 | 0.752344 | 0.0959509 | 0 | 0 |
| random_fourier | 0.9 | 5 | 0.765625 | 0.0913952 | 0 | 0 |
| random_fourier | 1 | 5 | 0.808594 | 0.0757156 | 0 | 0 |
| spsa_fourier | 0 | 5 | 0.975781 | 0.00780787 | 0 | 0 |
| spsa_fourier | 0.1 | 5 | 0.977344 | 0.00446432 | 0 | 0 |
| spsa_fourier | 0.2 | 5 | 0.977344 | 0.0103854 | 0 | 0 |
| spsa_fourier | 0.3 | 5 | 0.967187 | 0.0104417 | 0 | 0 |
| spsa_fourier | 0.4 | 5 | 0.942187 | 0.00701707 | 0 | 0 |
| spsa_fourier | 0.5 | 5 | 0.889062 | 0.0424629 | 0 | 0 |
| spsa_fourier | 0.6 | 5 | 0.764844 | 0.10426 | 0 | 0 |
| spsa_fourier | 0.7 | 5 | 0.741406 | 0.105295 | 0 | 0 |
| spsa_fourier | 0.8 | 5 | 0.754687 | 0.0760786 | 0 | 0 |
| spsa_fourier | 0.9 | 5 | 0.784375 | 0.0687103 | 0 | 0 |
| spsa_fourier | 1 | 5 | 0.832031 | 0.0534294 | 0 | 0 |

## Artifacts

- records CSV: `results/frustration_axis/frustration_axis_valid_ratio_records.csv`
- aggregates CSV: `results/frustration_axis/frustration_axis_valid_ratio_aggregates.csv`
- plot: `results/frustration_axis/valid_ratio_vs_j2_ratio.png`

## Scientific caution

This is a controlled local-proxy sweep, not a hardware claim. It isolates the frustration-axis dependence under fixed depth and shot budget; hardware routing and calibration-body deformation remain covered by `results/execution_body/`.
