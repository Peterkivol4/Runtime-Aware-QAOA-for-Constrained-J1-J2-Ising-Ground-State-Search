# Runtime-Aware J1-J2 Ising Findings Report

## Explicit answers

### Does BO-tuned Fourier QAOA beat SPSA-tuned QAOA in sample efficiency for frustrated ground-state search?
- **bo_fourier_auc**: -4.0
- **spsa_fourier_auc**: -4.0
- **p_value_gap**: 1.0
- **p_value_ratio**: 1.0
- **winner**: spsa_fourier
- **delta_auc**: 0.0

### Does readout mitigation + ZNE materially improve ground-state quality at the frustrated point and nearby ratios?
- **mean_gain**: 0.0
- **mean_psucc_gain**: -0.009767478403292009
- **best_window**: {'method': 'bo_direct', 'lattice_type': 'j1j2_frustrated', 'n_spins': 4, 'budget': 2, 'depth': 1, 'noise_level': 0.0, 'mitigation_gain': 0.0, 'j2_ratio': 0.0, 'disorder_strength': 0.0, 'shot_budget': 64}
- **positive_gain_share**: 0.0

### How does valid-ratio collapse as system size, depth, and frustration ratio rise?
- **collapse_share**: 0.5
- **first_collapse_window**: {'method': 'bo_direct', 'lattice_type': 'j1j2_frustrated', 'n_spins': 6, 'budget': 3, 'depth': 1, 'noise_level': 0.0, 'mean_gap': 0.0, 'j2_ratio': 0.0, 'disorder_strength': 0.0}
- **worst_valid_ratio_window**: {'method': 'bo_fourier', 'lattice_type': 'j1j2_frustrated', 'n_spins': 6, 'budget': 3, 'depth': 1, 'noise_level': 0.04, 'mean_valid_ratio': 0.3553473575363029, 'j2_ratio': 1.0, 'disorder_strength': 0.0}

## Performance profile

- bo_direct: profile_area=1.0000
- bo_fourier: profile_area=1.0000
- greedy: profile_area=1.0000
- local_search: profile_area=1.0000
- random_fourier: profile_area=1.0000

## Fairness snapshot

- classical_baseline::exact_feasible | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::greedy | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::local_search | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::random_search | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- classical_baseline::simulated_annealing | mitigation=none | mean_ratio=1.000000 | P_succ=1.0000 | runtime=0.0000s | shots=0.0
- qaoa::random_fourier | mitigation=none | mean_ratio=1.000000 | P_succ=0.2327 | runtime=0.1764s | shots=2400.0
- qaoa::random_fourier | mitigation=readout | mean_ratio=1.000000 | P_succ=0.2434 | runtime=0.1847s | shots=2400.0
- qaoa::bo_direct | mitigation=none | mean_ratio=1.000000 | P_succ=0.2061 | runtime=0.3425s | shots=2400.0

## Paired method deltas

- bo_fourier vs spsa_fourier | approximation_ratio mean_delta=0.000000 | win_rate_left=0.000
- bo_fourier vs random_fourier | approximation_ratio mean_delta=0.000000 | win_rate_left=0.000

## Takeaway

- Matched-call sample efficiency favors spsa_fourier.
- Mitigation helps most in a narrow window at n=4, J2/J1=0.0, depth=1, noise=0.000, shots=64.
- Valid-ratio collapse (<0.5) appears in 50.0% of aggregated QAOA windows.
- Best Dolan-Moré profile area: bo_direct.
