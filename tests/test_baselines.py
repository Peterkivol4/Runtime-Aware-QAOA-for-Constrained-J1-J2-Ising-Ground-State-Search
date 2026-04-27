from spinmesh_runtime.baselines import ClassicalBaselines
from spinmesh_runtime.config import RunDeck
from spinmesh_runtime.problem import IsingSpinProblem


def test_classical_baselines_return_exact_reference() -> None:
    cfg = RunDeck(n_spins=6, magnetization_m=0, classical_bo_iters=6, sa_steps=20)
    problem = IsingSpinProblem(cfg)
    baselines = ClassicalBaselines(problem, cfg)
    results = baselines.run_all()
    names = {record.method for record in results}
    assert "exact_feasible" in names
    exact = next(record for record in results if record.method == "exact_feasible")
    assert exact.best_energy == problem.exact_feasible_energy
