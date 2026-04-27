# Routing Deformation Report

## Fixed source experiment

- Hamiltonian: `j1j2_frustrated`, `n_spins = 6`, `J2/J1 = 0.5`, `M = 0`
- QAOA depth: `p = 2`
- Source circuit and frozen angles: held fixed for every row
- Varied execution body: topology model, initial layout, routing method, and transpiler optimization level

## Main empirical result

The same abstract QAOA circuit produced different physical observable errors after transpilation and noisy execution. The best routing body had correlation error `0.355222` with routing inflation `21`. The worst routing body had correlation error `0.410189` with routing inflation `83.6667`.

This supports the execution-body claim: routing is not just overhead bookkeeping; it changes the measured physics under noise.

Qiskit's basis translation decomposed routed SWAP structure into native `cx` operations for these generic backends, so `swap_count` is reported as direct surviving `swap` instructions and remains zero. The operative routing-deformation observables in this run are therefore transpiled depth, two-qubit gate count, and routing inflation.

## Aggregate routing statistics

| metric | min | max | mean |
| --- | --- | --- | --- |
| transpiled_depth | 378 | 1568 | 801.667 |
| two_qubit_gate_count | 96 | 400 | 243.278 |
| valid_sector_ratio | 0.293945 | 0.356445 | 0.321825 |
| correlation_error | 0.355222 | 0.410189 | 0.388181 |
| magnetization_error | 0.00179036 | 0.0472005 | 0.0230939 |

## Execution feature correlations

| execution_feature | corr_with_correlation_error | corr_with_valid_ratio |
| --- | --- | --- |
| transpiled_circuit_depth | 0.545278 | -0.472279 |
| two_qubit_gate_count | 0.617031 | -0.573988 |
| routing_inflation | 0.545278 | -0.472279 |

## Mean deformation by topology

| topology_model | records | mean_transpiled_circuit_depth | mean_two_qubit_gate_count | mean_valid_ratio | mean_correlation_error |
| --- | --- | --- | --- | --- | --- |
| forked_heavy_hex | 24 | 837.833 | 264.417 | 0.322021 | 0.390361 |
| line | 24 | 820.625 | 276.417 | 0.318726 | 0.391442 |
| star | 24 | 746.542 | 189 | 0.324727 | 0.38274 |

## Mean deformation by transpiler level

| transpiler_optimization_level | records | mean_transpiled_circuit_depth | mean_two_qubit_gate_count | mean_valid_ratio | mean_correlation_error |
| --- | --- | --- | --- | --- | --- |
| 0 | 18 | 1200.33 | 267.833 | 0.317763 | 0.393277 |
| 1 | 18 | 793.222 | 257.5 | 0.321153 | 0.387023 |
| 2 | 18 | 605.111 | 223.5 | 0.323893 | 0.384891 |
| 3 | 18 | 608 | 224.278 | 0.32449 | 0.387534 |

## Highest correlation-deformation rows

| topology_model | initial_layout_policy | routing_method | transpiler_optimization_level | transpiled_circuit_depth | two_qubit_gate_count | swap_count | routing_inflation | magnetization_error | correlation_error | observed_phase_label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| line | identity | basic | 0 | 1506 | 349 | 0 | 83.6667 | 0.0164388 | 0.410189 | invalid_sector_dominated |
| line | scattered | basic | 0 | 1568 | 400 | 0 | 87.1111 | 0.03125 | 0.407259 | invalid_sector_dominated |
| forked_heavy_hex | identity | basic | 0 | 1489 | 367 | 0 | 82.7222 | 0.0289714 | 0.40712 | invalid_sector_dominated |
| line | scattered | basic | 2 | 848 | 376 | 0 | 47.1111 | 0.0364583 | 0.405027 | invalid_sector_dominated |
| star | reversed | basic | 3 | 655 | 247 | 0 | 36.3889 | 0.0159505 | 0.40126 | invalid_sector_dominated |
| star | scattered | basic | 0 | 1261 | 280 | 0 | 70.0556 | 0.00179036 | 0.400842 | invalid_sector_dominated |
| star | scattered | basic | 2 | 679 | 250 | 0 | 37.7222 | 0.0291341 | 0.399168 | invalid_sector_dominated |
| line | reversed | basic | 2 | 782 | 329 | 0 | 43.4444 | 0.0232747 | 0.39847 | invalid_sector_dominated |
| line | reversed | basic | 3 | 782 | 329 | 0 | 43.4444 | 0.0141602 | 0.39847 | invalid_sector_dominated |
| line | identity | sabre | 0 | 1069 | 232 | 0 | 59.3889 | 0.0183919 | 0.397633 | invalid_sector_dominated |
