import numpy as np

from hybrid_qaoa_portfolio.config import RunDeck
from hybrid_qaoa_portfolio.problem import IsingSpinProblem


def test_fixed_magnetization_maps_to_cardinality() -> None:
    cfg = RunDeck(n_spins=6, magnetization_m=0)
    problem = IsingSpinProblem(cfg)
    assert problem.budget == 3
    assert cfg.budget == 3

    cfg = RunDeck(n_spins=6, magnetization_m=2)
    problem = IsingSpinProblem(cfg)
    assert problem.budget == 4
    assert cfg.budget == 4


def test_qubo_matches_direct_ising_energy_on_two_spin_toy() -> None:
    cfg = RunDeck(n_spins=2, magnetization_m=0, lattice_type="random_bond", disorder_strength=0.0, h_field=0.0)
    J = np.array([[0.0, -1.25], [-1.25, 0.0]])
    h = np.array([0.4, -0.1])
    problem = IsingSpinProblem(cfg, J=J, h=h)

    direct = {bitstring: problem.evaluate_ising_energy(bitstring) for bitstring in problem.all_bitstrings()}
    qubo = {bitstring: problem.evaluate_energy(bitstring) for bitstring in problem.all_bitstrings()}

    assert np.isclose(problem.Q[0, 1], -4.0 * J[0, 1])
    assert np.isclose(problem.Q[1, 0], 0.0)
    assert set(direct) == set(qubo)
    assert all(np.isclose(direct[key], qubo[key]) for key in direct)
    assert min(direct, key=direct.get) == min(qubo, key=qubo.get)


def test_qubo_matches_direct_ising_energy_on_four_spin_sector() -> None:
    cfg = RunDeck(n_spins=4, magnetization_m=0, lattice_type="j1j2_frustrated", disorder_strength=0.0, h_field=0.0)
    J = np.array(
        [
            [0.0, -1.0, -1.0, -0.5],
            [-1.0, 0.0, -0.5, -1.0],
            [-1.0, -0.5, 0.0, -1.0],
            [-0.5, -1.0, -1.0, 0.0],
        ]
    )
    h = np.array([0.0, 0.2, -0.1, 0.0])
    problem = IsingSpinProblem(cfg, J=J, h=h)

    feasible = problem.feasible_bitstrings
    direct = [problem.evaluate_ising_energy(bitstring) for bitstring in feasible]
    qubo = [problem.evaluate_energy(bitstring) for bitstring in feasible]

    assert np.allclose(direct, qubo)
    assert feasible[int(np.argmin(direct))] == feasible[int(np.argmin(qubo))]


def test_feasible_bitstrings_and_remap_respect_sector() -> None:
    cfg = RunDeck(n_spins=5, magnetization_m=-1)
    problem = IsingSpinProblem(cfg)
    assert all(problem.is_valid(bitstring) for bitstring in problem.feasible_bitstrings)
    assert all(bitstring.count("1") == problem.budget for bitstring in problem.feasible_bitstrings)

    remapped_high = problem.remap_to_valid("11110")
    remapped_low = problem.remap_to_valid("00000")
    assert problem.is_valid(remapped_high)
    assert problem.is_valid(remapped_low)


def test_bitstring_to_spins_and_energy_gap_are_reportable() -> None:
    cfg = RunDeck(n_spins=4, magnetization_m=0, lattice_type="afm_uniform", disorder_strength=0.0, h_field=0.0)
    problem = IsingSpinProblem(cfg)
    spins = problem.bitstring_to_spins("1010")
    assert np.array_equal(spins, np.array([1, -1, 1, -1]))
    assert problem.energy_gap_to_second_lowest is not None
    assert problem.energy_gap_to_second_lowest >= 0.0


def test_frustration_index_distinguishes_unfrustrated_and_frustrated_instances() -> None:
    cfg_unfrustrated = RunDeck(
        n_spins=4,
        magnetization_m=0,
        lattice_type="afm_uniform",
        j2_coupling=0.0,
        disorder_strength=0.0,
        h_field=0.0,
    )
    unfrustrated = IsingSpinProblem(cfg_unfrustrated)
    assert unfrustrated.frustration_index == 0.0

    cfg_frustrated = RunDeck(n_spins=4, magnetization_m=0, lattice_type="j1j2_frustrated", disorder_strength=0.0, h_field=0.0)
    frustrated = IsingSpinProblem(cfg_frustrated)
    assert frustrated.frustration_index > 0.0
