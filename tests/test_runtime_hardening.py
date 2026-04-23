from pathlib import Path

from qiskit.quantum_info import SparsePauliOp

from hybrid_qaoa_portfolio.config import RunDeck, TailBatch
from hybrid_qaoa_portfolio.optimization import GaussianProcessBayesOptimizer
from hybrid_qaoa_portfolio.pipeline import PenaltyController
from hybrid_qaoa_portfolio.quantum import _observable_for_isa
from hybrid_qaoa_portfolio.runtime_support import RuntimeSamplerFactory


def test_contextual_bo_accepts_penalty_context() -> None:
    opt = GaussianProcessBayesOptimizer(n_params=4, n_init=2, seed=7, context_dim=3)
    x1 = opt.suggest(context=[0.0, 0.1, 0.0])
    opt.observe(x1, 1.0, context=[0.0, 0.1, 0.0])
    x2 = opt.suggest(context=[0.2, 0.3, 0.5])
    opt.observe(x2, 0.5, context=[0.2, 0.3, 0.5])
    x3 = opt.suggest(context=[0.8, 0.9, 1.0])
    assert x3.shape == (4,)
    assert len(opt.train_x) == 2
    assert opt.train_x[0].shape == (7,)


def test_augmented_lagrangian_updates_only_at_epoch_boundaries() -> None:
    cfg = RunDeck(constraint_handling="penalty", penalty_schedule="augmented_lagrangian", penalty_epoch_length=3)
    controller = PenaltyController.create(cfg, total_steps=6)
    before = controller.state(1)
    batch = TailBatch(cvar=1.0, valid_ratio=0.2, variance=0.0, feasible_best=1.0, raw_best=1.0, total_shots=10, backend="proxy")
    controller.observe(batch, 1)
    mid = controller.state(2)
    controller.observe(batch, 2)
    still_mid = controller.state(3)
    controller.observe(batch, 3)
    after_boundary = controller.state(4)
    assert mid.quadratic_strength == before.quadratic_strength
    assert still_mid.quadratic_strength == before.quadratic_strength
    assert after_boundary.quadratic_strength >= before.quadratic_strength
    assert after_boundary.epoch == 1


def test_noise_profile_from_snapshot_uses_realistic_averages() -> None:
    snapshot = {
        "qubits": [
            {"t1": 100.0, "t2": 120.0, "readout_error": 0.02},
            {"t1": 200.0, "t2": 220.0, "readout_error": 0.04},
        ],
        "instruction_errors": {"cx": [0.01, 0.03], "rz": [0.001]},
    }
    profile = RuntimeSamplerFactory.noise_profile_from_snapshot(snapshot)
    assert profile["t1_time"] == 150.0
    assert profile["t2_time"] == 170.0
    assert abs(profile["readout_p10"] - 0.03) < 1e-12
    assert abs(profile["depol_error"] - ((0.01 + 0.03 + 0.001) / 3.0)) < 1e-12


def test_observable_for_isa_expands_to_transpiled_width() -> None:
    class DummyIsaCircuit:
        layout = None
        num_qubits = 5

    observable = SparsePauliOp.from_list([("ZI", 1.0)])
    aligned = _observable_for_isa(observable, DummyIsaCircuit())

    assert aligned.num_qubits == 5
