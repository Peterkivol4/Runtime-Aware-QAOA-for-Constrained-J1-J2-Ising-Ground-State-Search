# Runtime-Aware QAOA Findings Report

## Explicit answers

### Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency?
- **bo_fourier_auc**: -0.21027375991728695
- **spsa_fourier_auc**: -0.209012877550687
- **p_value_gap**: 0.6022897385697255
- **p_value_ratio**: 0.6022897385697255
- **winner**: bo_fourier
- **delta_auc**: 0.0012608823665999358

### Does readout mitigation + ZNE materially improve feasible-energy quality under shot noise?
- **mean_gain**: 0.002373696574502972
- **mean_psucc_gain**: -0.03187726488560426
- **best_window**: {'method': 'spsa_fourier', 'regime': 'clustered', 'n_assets': 6, 'budget': 3, 'depth': 1, 'noise_level': 0.04, 'mitigation_gain': 0.023170157870271935, 'shot_budget': 32}
- **positive_gain_share**: 0.1875

### How does valid-ratio collapse as asset count, depth, and noise rise?
- **collapse_share**: 0.0
- **first_collapse_window**: None
- **worst_valid_ratio_window**: {'method': 'bo_direct', 'regime': 'clustered', 'n_assets': 6, 'budget': 3, 'depth': 2, 'noise_level': 0.0, 'mean_valid_ratio': 0.5288437641891086}

## Performance profile

- local_search: profile_area=1.0000
- random_search: profile_area=1.0000
- simulated_annealing: profile_area=1.0000
- random_fourier: profile_area=0.8672
- bo_direct: profile_area=0.8245

## Fairness snapshot

- classical_baseline::exact_feasible | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::local_search | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::random_search | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::simulated_annealing | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- qaoa::random_fourier | mitigation=readout | mean_ratio=1.018312 | P_succ=0.4724 | runtime=0.1357s | shots=640.0
- qaoa::random_fourier | mitigation=none | mean_ratio=1.018312 | P_succ=0.4355 | runtime=0.1365s | shots=640.0
- qaoa::random_fourier | mitigation=readout+zne | mean_ratio=1.018312 | P_succ=0.4164 | runtime=0.2375s | shots=800.0
- qaoa::bo_direct | mitigation=readout+zne | mean_ratio=1.018312 | P_succ=0.3593 | runtime=0.2383s | shots=800.0

## Paired method deltas

- bo_fourier vs spsa_fourier | approximation_ratio mean_delta=-0.005099 | win_rate_left=0.250
- bo_fourier vs random_fourier | approximation_ratio mean_delta=0.005784 | win_rate_left=0.000

## Takeaway

- Matched-call sample efficiency favors bo_fourier.
- Mitigation helps most in a narrow window at n=6, depth=1, noise=0.040, shots=32.
- Valid-ratio collapse (<0.5) appears in 0.0% of aggregated QAOA windows.
- Best Dolan-Moré profile area: local_search.
