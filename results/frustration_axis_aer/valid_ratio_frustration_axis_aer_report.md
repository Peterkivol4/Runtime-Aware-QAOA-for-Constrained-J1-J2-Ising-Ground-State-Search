# Aer Routed Valid-Ratio Collapse Across the Frustration Axis

## Fixed sweep design

- backend model: `AerSimulator` with generic routed backend
- topology model: `forked_heavy_hex`
- transpiler optimization level: `1`
- routing method: `sabre`
- `n_spins`: `6`
- QAOA depth: `p = 2`
- shots per ratio/seed: `2048`
- seeds: `910` through `912`
- `J2/J1` ratios: `0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0`
- elapsed wall-clock seconds: `17.50`

The source-level angles are selected by the same deterministic statevector search procedure for each ratio/seed, then the measured circuit is transpiled and sampled under the same execution body.

## Main interpretation

The hardware-like routed Aer sweep reproduces valid-sector collapse, but the collapse is broad rather than sharply localized at `J2/J1 = 0.5`.

- center mean valid ratio: `0.316569`
- endpoint mean valid ratio: `0.31543`
- adjacent-shoulder mean valid ratio (`0.4`, `0.6`): `0.315837`
- center minus endpoints: `0.00113932`
- center minus shoulders: `0.000732422`

## Aggregate table

| j2_ratio | n | mean_valid_ratio | ci95_valid_ratio | collapse_fraction | mean_correlation_error | mean_routing_inflation | mean_two_qubit_gate_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 3 | 0.31429 | 0.0118807 | 1 | 0.401542 | 33.6296 | 196 |
| 0.1 | 3 | 0.315267 | 0.0124332 | 1 | 0.400984 | 32.6481 | 190 |
| 0.2 | 3 | 0.315592 | 0.0128439 | 1 | 0.401542 | 34.5741 | 202 |
| 0.3 | 3 | 0.316243 | 0.0105467 | 1 | 0.400679 | 32.6481 | 190 |
| 0.4 | 3 | 0.316406 | 0.0102332 | 1 | 0.400912 | 32.7222 | 190 |
| 0.5 | 3 | 0.316569 | 0.0109723 | 1 | 0.400586 | 33.5926 | 196 |
| 0.6 | 3 | 0.315267 | 0.0100729 | 1 | 0.400493 | 33.5556 | 196 |
| 0.7 | 3 | 0.316569 | 0.0104449 | 1 | 0.392863 | 33.6296 | 196 |
| 0.8 | 3 | 0.316732 | 0.0111927 | 1 | 0.382249 | 33.6296 | 196 |
| 0.9 | 3 | 0.317546 | 0.00965501 | 1 | 0.361091 | 33.6667 | 196 |
| 1 | 3 | 0.316569 | 0.00836756 | 1 | 0.36137 | 32.6852 | 190 |

## Artifacts

- records CSV: `/Users/hirrreshsundrq/Documents/New project/runtime_aware_qaoa_portfolio_repo_full_rebuilt_v28/results/frustration_axis_aer/frustration_axis_aer_records.csv`
- aggregates CSV: `/Users/hirrreshsundrq/Documents/New project/runtime_aware_qaoa_portfolio_repo_full_rebuilt_v28/results/frustration_axis_aer/frustration_axis_aer_aggregates.csv`
- plot: `/Users/hirrreshsundrq/Documents/New project/runtime_aware_qaoa_portfolio_repo_full_rebuilt_v28/results/frustration_axis_aer/valid_ratio_vs_j2_ratio_aer.png`
