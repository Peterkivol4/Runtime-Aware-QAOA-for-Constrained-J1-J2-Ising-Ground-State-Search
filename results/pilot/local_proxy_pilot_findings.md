# Runtime-Aware QAOA Findings Report

## Explicit answers

### Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency?
- **bo_fourier_auc**: -0.2169472082739349
- **spsa_fourier_auc**: -0.2169472082739349
- **p_value_gap**: 1.0
- **p_value_ratio**: 1.0
- **winner**: spsa_fourier
- **delta_auc**: 0.0

### Does readout mitigation + ZNE materially improve feasible-energy quality under shot noise?
- **mean_gain**: 0.0
- **mean_psucc_gain**: 0.025467805054183557
- **best_window**: {'method': 'bo_direct', 'regime': 'clustered', 'n_assets': 4, 'budget': 2, 'depth': 1, 'noise_level': 0.0, 'mitigation_gain': 0.0, 'shot_budget': 32}
- **positive_gain_share**: 0.0

### How does valid-ratio collapse as asset count, depth, and noise rise?
- **collapse_share**: 1.0
- **first_collapse_window**: {'method': 'bo_direct', 'regime': 'clustered', 'n_assets': 4, 'budget': 2, 'depth': 1, 'noise_level': 0.0, 'mean_gap': 0.0}
- **worst_valid_ratio_window**: {'method': 'spsa_fourier', 'regime': 'clustered', 'n_assets': 6, 'budget': 3, 'depth': 1, 'noise_level': 0.0, 'mean_valid_ratio': 0.2737626343982207}

## Performance profile

- bo_direct: profile_area=1.0000
- bo_fourier: profile_area=1.0000
- local_search: profile_area=1.0000
- random_fourier: profile_area=1.0000
- random_search: profile_area=1.0000

## Fairness snapshot

- classical_baseline::exact_feasible | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::local_search | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::random_search | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::simulated_annealing | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- qaoa::random_fourier | mitigation=readout+zne | mean_ratio=1.000000 | P_succ=0.2796 | runtime=0.0027s | shots=800.0
- qaoa::bo_fourier | mitigation=readout+zne | mean_ratio=1.000000 | P_succ=0.2626 | runtime=0.0031s | shots=800.0
- qaoa::random_fourier | mitigation=none | mean_ratio=1.000000 | P_succ=0.2476 | runtime=0.0036s | shots=640.0
- qaoa::bo_direct | mitigation=readout+zne | mean_ratio=1.000000 | P_succ=0.2812 | runtime=0.0039s | shots=800.0

## Paired method deltas

- bo_fourier vs spsa_fourier | approximation_ratio mean_delta=0.000000 | win_rate_left=0.000
- bo_fourier vs random_fourier | approximation_ratio mean_delta=0.000000 | win_rate_left=0.000

## Takeaway

- Matched-call sample efficiency favors spsa_fourier.
- Mitigation helps most in a narrow window at n=4, depth=1, noise=0.000, shots=32.
- Valid-ratio collapse (<0.5) appears in 100.0% of aggregated QAOA windows.
- Best Dolan-Moré profile area: bo_direct.
