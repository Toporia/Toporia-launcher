"""test_interpolation.py — the material law as a part of its own.

SIMP was hard-coded in the Q4 engine; it is now one interpolation among
others, chosen in the solver like the filters.  These tests pin that the
default reproduces the old behaviour, that another law really changes the
result, and that the choice is visible and recorded.
"""

import json

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single
from toporia.engine.pipeline import pipeline_parts, pipeline_stages
from toporia.plugins.interpolations import INTERPOLATIONS
from toporia.plugins.interpolations.ramp import RAMP
from toporia.plugins.interpolations.simp import SIMP
from toporia.plugins.problems import get_run

SMALL = {"m": 0.3, "max_iter": 8, "tol": 0.0, "save_every": 0}


def _run(**values):
    return get_run("MBB Beam").updated(**{**SMALL, **values})


def _final_density(run):
    method = initialized_method(run)
    for iteration in range(1, run.solver.max_iter + 1):
        method.step(iteration)
    return method.get_density()


def test_both_laws_are_registered_and_simp_is_the_default():
    assert INTERPOLATIONS.names() == ["simp", "ramp"]
    assert _run().solver.interpolation == {"type": "simp"}


def test_the_default_is_exactly_what_the_engine_did_before():
    """SIMP p = 3 written out by hand, as the Q4 engine wrote it before the law was a part."""
    rho = np.random.default_rng(0).uniform(0.0, 1.0, 50)
    law = SIMP(3.0)
    assert np.array_equal(law.stiffness(rho, 1.0, 1e-9), 1e-9 + rho ** 3.0 * (1.0 - 1e-9))
    assert np.array_equal(law.slope(rho, 1.0, 1e-9), 3.0 * (1.0 - 1e-9) * rho ** 2.0)


def test_another_law_changes_the_design():
    simp = _final_density(_run())
    ramp = _final_density(_run(interpolation={"type": "ramp", "q": 8.0}))
    assert np.max(np.abs(simp - ramp)) > 1e-3


def test_ramp_has_a_slope_at_void_where_simp_has_none():
    """RAMP's reason to exist: a void element still feels a sensitivity."""
    void = np.array([0.0])
    assert SIMP(3.0).slope(void, 1.0, 1e-9)[0] == 0.0
    assert RAMP(8.0).slope(void, 1.0, 1e-9)[0] == pytest.approx(1.0 / 9.0, rel=1e-6)


def test_the_law_is_shown_in_the_pipeline_and_recorded_with_the_result(tmp_path):
    run = _run(interpolation={"type": "ramp", "q": 6.0}).with_output_dir(tmp_path)
    assert dict(pipeline_stages(run))["Material"] == "RAMP (rational)"
    assert ("interpolation", RAMP) in pipeline_parts(run)
    run_single(run)
    record = json.loads((tmp_path / "run.json").read_text())
    assert record["solver"]["definition"]["interpolation"] == {"type": "ramp", "q": 6.0}
    assert [p["name"] for p in record["parts"] if p["kind"] == "interpolation"] == ["ramp"]


def test_a_misspelt_law_parameter_fails_before_computing():
    with pytest.raises(ValueError, match="pnal"):
        initialized_method(_run(interpolation={"type": "simp", "pnal": 4.0}))


def test_the_penalty_is_no_longer_a_q4_method_parameter():
    """It moved to interpolation.penal; the old path is refused instead of silently ignored."""
    with pytest.raises(ValueError, match="penal"):
        initialized_method(_run(method_params={"penal": 4.0}))


def test_a_model_with_its_own_law_says_so():
    stages = dict(pipeline_stages(_run(method="pymoto")))
    assert stages["Material"] == "inside the model"
    assert not any(kind == "interpolation" for kind, _ in pipeline_parts(_run(method="levelset")))
