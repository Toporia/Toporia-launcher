"""External reference values, not regenerated internal golden baselines."""

import json

import pytest

from experiments.original_references import REFERENCES, rerun_matlab, validate, validate_mma

DATA = json.loads(REFERENCES.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda case: case["name"])
def test_python_matches_unmodified_matlab_printed_precision(case):
    result = validate(case)
    assert result["iterations"] == case["iterations"]
    for key in ("first_reported_compliance", "last_reported_compliance"):
        assert result[key] == pytest.approx(case[key], rel=0., abs=5.01e-5)
    assert result["final_mean_density"] == pytest.approx(case["reported_volume"], rel=0., abs=5.01e-4)
    if "final_mean_density" in case:
        assert result["final_mean_density"] == pytest.approx(case["final_mean_density"], abs=1e-10)


def test_original_rerun_refuses_changed_source_before_starting_matlab(tmp_path):
    (tmp_path / "top88.m").write_text("Changed source", encoding="utf-8")
    with pytest.raises(ValueError, match="Source hash changed"):
        rerun_matlab(DATA, tmp_path, "a-matlab-executable-that-must-not-run")


def test_mmapy_matches_captured_matlab_mma_and_the_analytic_optimum():
    pytest.importorskip("mmapy")
    import numpy as np

    expected = DATA["optimizer_reference"]
    result = validate_mma()
    assert result["iterations"] == expected["iterations"]
    for key in ("first_design", "final_design"):
        np.testing.assert_allclose(result[key], expected[key], rtol=0, atol=1e-10)
    for key in ("initial_objective", "final_objective", "final_budget", "final_multiplier"):
        assert result[key] == pytest.approx(expected[key], rel=0, abs=1e-10)
    assert result["final_budget"] <= 2.4
    assert result["final_objective"] == pytest.approx(expected["analytic_objective"], rel=2e-9)
