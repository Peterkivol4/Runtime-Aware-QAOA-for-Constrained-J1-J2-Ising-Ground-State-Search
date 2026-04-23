# Runtime-Aware J1-J2 Ising Findings Report

## Explicit answers

### Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency for frustrated ground-state search?
- **bo_fourier_auc**: -5.3484037319116915
- **spsa_fourier_auc**: -5.3484037319116915
- **p_value_gap**: 1.0
- **p_value_ratio**: 1.0
- **winner**: spsa_fourier
- **delta_auc**: 0.0

### Does readout mitigation + ZNE materially improve ground-state quality at the frustrated point and nearby ratios?
- **mean_gain**: 0.0
- **mean_psucc_gain**: -0.004242183810742673
- **best_window**: {'method': 'bo_direct', 'lattice_type': 'j1j2_frustrated', 'n_spins': 4, 'budget': 2, 'depth': 1, 'noise_level': 0.0, 'mitigation_gain': 0.0, 'j2_ratio': 0.0, 'disorder_strength': 0.0, 'shot_budget': 64}
- **positive_gain_share**: 0.0

### How does valid-ratio collapse as system size, depth, and frustration ratio rise?
- **collapse_share**: 0.07083333333333333
- **first_collapse_window**: {'method': 'spsa_fourier', 'lattice_type': 'j1j2_frustrated', 'n_spins': 6, 'budget': 3, 'depth': 2, 'noise_level': 0.0, 'mean_gap': 0.0, 'j2_ratio': 0.75, 'disorder_strength': 0.3}
- **worst_valid_ratio_window**: {'method': 'spsa_fourier', 'lattice_type': 'j1j2_frustrated', 'n_spins': 6, 'budget': 3, 'depth': 2, 'noise_level': 0.0, 'mean_valid_ratio': 0.10641450168794754, 'j2_ratio': 1.0, 'disorder_strength': 0.3}

## Performance profile

- bo_direct: profile_area=1.0000
- bo_fourier: profile_area=1.0000
- random_fourier: profile_area=1.0000
- random_search: profile_area=1.0000
- spsa_fourier: profile_area=1.0000

## Fairness snapshot

- classical_baseline::exact_feasible | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::random_search | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- qaoa::random_fourier | mitigation=readout+zne | mean_ratio=1.000000 | P_succ=0.7612 | runtime=0.0168s | shots=3872.0
- qaoa::bo_direct | mitigation=readout+zne | mean_ratio=1.000000 | P_succ=0.7589 | runtime=0.0171s | shots=3872.0
- qaoa::bo_fourier | mitigation=readout+zne | mean_ratio=1.000000 | P_succ=0.7522 | runtime=0.0183s | shots=3872.0
- qaoa::random_fourier | mitigation=readout | mean_ratio=1.000000 | P_succ=0.7845 | runtime=0.0189s | shots=3200.0
- qaoa::random_fourier | mitigation=none | mean_ratio=1.000000 | P_succ=0.7669 | runtime=0.0193s | shots=3200.0
- qaoa::spsa_fourier | mitigation=readout | mean_ratio=1.000000 | P_succ=0.7811 | runtime=0.0203s | shots=8320.0

## Paired method deltas

- bo_fourier vs spsa_fourier | approximation_ratio mean_delta=0.000000 | win_rate_left=0.000
- bo_fourier vs random_fourier | approximation_ratio mean_delta=0.000000 | win_rate_left=0.000

## Takeaway

- Matched-call sample efficiency favors spsa_fourier.
- Mitigation helps most in a narrow window at n=4, J2/J1=0.0, depth=1, noise=0.000, shots=64.
- Valid-ratio collapse (<0.5) appears in 7.1% of aggregated QAOA windows.
- Best Dolan-Moré profile area: bo_direct.
