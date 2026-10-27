"""External reference values, not regenerated internal golden baselines."""

import json

import pytest

from experiments.original_references import REFERENCES, rerun_matlab, validate

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
