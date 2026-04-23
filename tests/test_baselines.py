from hybrid_qaoa_portfolio.baselines import ClassicalBaselines
from hybrid_qaoa_portfolio.config import RunDeck
from hybrid_qaoa_portfolio.problem import PortfolioProblem


def test_classical_baselines_return_exact_reference() -> None:
    cfg = RunDeck(n_assets=6, budget=3, classical_bo_iters=6, sa_steps=20)
    problem = PortfolioProblem(cfg)
    baselines = ClassicalBaselines(problem, cfg)
    results = baselines.run_all()
    names = {record.method for record in results}
    assert "exact_feasible" in names
    exact = next(record for record in results if record.method == "exact_feasible")
    assert exact.best_energy == problem.exact_feasible_energy
