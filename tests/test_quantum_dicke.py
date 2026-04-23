from math import comb

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from hybrid_qaoa_portfolio.config import RunDeck
from ionmesh_runtime._internal.quantum import _build_parametric_qaoa_circuit, _prepare_dicke_state


def _support(bit_probabilities: dict[str, float]) -> dict[str, float]:
    return {bitstring: prob for bitstring, prob in bit_probabilities.items() if prob > 1e-9}


def test_prepare_dicke_state_is_normalized_and_sector_limited() -> None:
    n = 4
    k = 2
    circuit = QuantumCircuit(n)
    _prepare_dicke_state(n, k, circuit)
    state = Statevector.from_instruction(circuit)
    probabilities = _support(state.probabilities_dict())

    assert np.isclose(sum(probabilities.values()), 1.0)
    assert len(probabilities) == comb(n, k)
    assert {bitstring.count("1") for bitstring in probabilities} == {k}
    assert len({round(prob, 10) for prob in probabilities.values()}) == 1


def test_prepare_dicke_state_handles_edge_cases() -> None:
    cases = [(4, 0, 1), (4, 4, 1), (4, 1, 4), (4, 3, 4)]
    for n, k, expected_support in cases:
        circuit = QuantumCircuit(n)
        _prepare_dicke_state(n, k, circuit)
        probabilities = _support(Statevector.from_instruction(circuit).probabilities_dict())
        assert len(probabilities) == expected_support
        assert {bitstring.count("1") for bitstring in probabilities} == {k}


def test_qaoa_circuit_uses_dicke_initialization_in_main_path() -> None:
    cfg = RunDeck(
        n_spins=4,
        magnetization_m=0,
        depth=1,
        fourier_modes=1,
        base_shots=16,
        runtime_mode="aer",
    )
    circuit = _build_parametric_qaoa_circuit(cfg, gamma=np.array([0.0]), beta=np.array([0.0]), measure=False)
    probabilities = _support(Statevector.from_instruction(circuit).probabilities_dict())

    assert len(probabilities) == comb(cfg.n_spins, cfg.budget)
    assert {bitstring.count("1") for bitstring in probabilities} == {cfg.budget}
