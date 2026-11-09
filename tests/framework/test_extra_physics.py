"""test_extra_physics.py — several physics on one design field (To do item 9).

An extra physics, with its own material law, is solved on the same density as the
main one when a variable asks for it; its responses keep exact gradients, it is
solved once per design, and a bad spec is refused before the run.
"""

from dataclasses import replace

import numpy as np
import pytest

from toporia_core.checks.common import gradient_check
from toporia_core.checks.report import Report
from toporia_core.engine.loop import initialized_method
from toporia_core.framework.companions import check_extra_physics
from toporia_core.framework.parts.method import OBJECTIVE
from toporia_core.framework.problem import files
from toporia_library.models.q4 import Q4Model
from toporia_library.problems import get_run

EXTRA = [{"model": "q4_heat", "interpolation": {"type": "simp", "penal": 1.0}}]
VARIABLES = [{"name": "heat", "type": "thermal_compliance", "physics": "q4_heat"}]
OBJECTIVE_SPEC = {"type": "combined", "combine": "sum",
                  "terms": [{"type": "compliance"}, {"type": "variable", "variable": "heat", "weight": 0.5}]}


def _run(**solver):
    run = get_run("MBB Beam").updated(method="q4+mma", tol=0.0, **solver)
    return replace(run, scenario=replace(run.scenario, extra_physics=EXTRA, variables=VARIABLES,
                                         objective=OBJECTIVE_SPEC))


def test_a_response_on_an_extra_physics_has_an_exact_gradient():
    method = initialized_method(_run(max_iter=1))
    model = method._model
    density = np.random.default_rng(2).uniform(0.3, 0.9, model.problem.shape)
    state = model.engine.solve(density)
    result = model.objective.evaluate(state)
    report = Report("extra physics")
    gradient_check(lambda d: model.objective.evaluate(model.engine.solve(d), gradient=False).value,
                   result.gradient, density, np.ones(density.shape, bool), report, "combined")
    report.assert_ok()


def test_an_extra_physics_is_solved_once_per_design(monkeypatch):
    method = initialized_method(_run(max_iter=1))
    companion = method._model.engine.companions["q4_heat"]
    calls = []
    real = companion.engine.solve
    monkeypatch.setattr(companion.engine, "solve", lambda d: calls.append(1) or real(d))
    density = np.full(method._model.problem.shape, 0.5)
    first = companion.solve(density)
    assert companion.solve(density.copy()) is first and len(calls) == 1
    companion.solve(density * 0.9)
    assert len(calls) == 2


@pytest.mark.parametrize("specs, message", [
    ([{"interpolation": {}}], "needs a 'model'"),
    ([{"model": "q4_heat", "colour": 1}], "no field"),
    ([{"model": "q4_heat"}, {"model": "q4_heat"}], "named twice"),
    ([{"model": "q4"}], "named twice"),                 # the main physics itself
    ([{"model": "h8_heat"}], "dimensions"),
])
def test_bad_extra_physics_are_refused(specs, message):
    with pytest.raises(ValueError, match=message):
        check_extra_physics(specs, Q4Model)


def test_a_variable_on_a_physics_that_is_not_there_is_refused():
    run = _run(max_iter=1)
    run = replace(run, scenario=replace(run.scenario, extra_physics=[]))
    with pytest.raises(ValueError, match="no extra physics 'q4_heat'"):
        initialized_method(run)


def test_extra_physics_are_saved_and_a_short_run_improves_both(tmp_path):
    run = _run(max_iter=6)
    loaded = files.load(files.save(run.scenario, tmp_path / "s.json"), "scenario")
    assert loaded.extra_physics == EXTRA and loaded.variables == VARIABLES
    method = initialized_method(run)
    history = []
    for i in range(6):
        method.step(i + 1)
        history.append(method.get_responses())
    assert history[-1][OBJECTIVE] < history[0][OBJECTIVE]
    assert history[-1]["term:compliance"] < history[0]["term:compliance"]
    assert history[-1]["var:heat"] < history[0]["var:heat"]
