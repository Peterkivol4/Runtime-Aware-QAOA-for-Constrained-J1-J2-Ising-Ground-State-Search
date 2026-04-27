from spinmesh_runtime.config import RunDeck


def test_dynamic_shots_scales_with_cvar_alpha() -> None:
    cfg = RunDeck(base_shots=100, cvar_alpha=0.25)
    assert cfg.dynamic_shots == 400


def test_validate_rejects_invalid_budget() -> None:
    cfg = RunDeck(n_spins=3, magnetization_m=5)
    try:
        cfg.validate()
    except ValueError as exc:
        assert "budget" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid budget")
