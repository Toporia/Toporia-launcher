"""test_variables.py — the problem as a space of variables (To do items 1 + 2).

A scenario's variables are measured quantities or formulas of other variables; they are
validated, recorded every iteration, saved with the scenario, and become an objective,
a term or a constraint through the "variable" response with exact gradients.
"""

from dataclasses import replace

import numpy as np
import pytest

from toporia_core.checks.common import gradient_check
from toporia_core.checks.report import Report
from toporia_core.engine.loop import initialized_method
from toporia_core.framework.parts.method import OBJECTIVE
from toporia_core.framework.parts.response import CONSTRAINT_ROLE
from toporia_core.framework.problem import files
from toporia_core.framework.problem.mesh import make_problem
from toporia_core.framework.registries import check_responses, resolve_response
from toporia_core.framework.variables import VariableSet, check_variables, variable_space
from toporia_library.models.q4 import Q4Model
from toporia_library.models.q4_heat import Q4HeatModel
from toporia_library.problems import get_run

VARIABLES = [{"name": "s", "type": "peak_stress", "p": 6.0},
             {"name": "ratio", "expression": "compliance * s / volume"},
             {"name": "twice", "expression": "2 * ratio"}]


def _scenario(**changes):
    run = get_run("MBB Beam")
    return replace(run.scenario, variables=VARIABLES, **changes)


def _engine(scenario):
    problem = make_problem(scenario, 2)
    engine = Q4Model.physics()
    engine.initialize(problem, {p.name: p.default for p in Q4Model.params})
    return engine, problem


def test_the_variable_space_lists_built_in_and_own_variables():
    rows = variable_space(Q4Model.physics, VARIABLES)
    names = {name: kind for name, _, kind in rows}
    assert names["compliance"] == names["volume"] == names["peak_stress"] == "built in"
    assert "thermal_compliance" not in names                    # not on an elastic physics
    assert names["s"] == "measured" and names["ratio"] == names["twice"] == "derived"
    assert "thermal_compliance" in {n for n, _, _ in variable_space(Q4HeatModel.physics)}


def test_derived_variables_have_exact_gradients():
    scenario = _scenario()
    engine, problem = _engine(scenario)
    variables = VariableSet(engine, problem, scenario.variables)
    density = np.random.default_rng(5).uniform(0.3, 0.9, problem.shape)
    values = variables.evaluate(engine.solve(density), gradient=True)
    assert values["twice"][0] == pytest.approx(2 * values["ratio"][0])
    assert values["ratio"][0] == pytest.approx(values["compliance"][0] * values["s"][0] / values["volume"][0])
    report = Report("variables")
    gradient_check(lambda d: variables.evaluate(engine.solve(d))["twice"][0], values["twice"][1],
                   density, np.ones(density.shape, bool), report, "twice")
    report.assert_ok()


@pytest.mark.parametrize("specs, message", [
    ([{"name": "a b", "type": "volume"}], "Python name"),
    ([{"name": "a", "type": "volume"}, {"name": "a", "type": "volume"}], "used twice"),
    ([{"name": "a"}], "either a 'type'"),
    ([{"name": "a", "type": "volume", "expression": "1"}], "either a 'type'"),
    ([{"name": "a", "expression": "b"}, {"name": "b", "expression": "a + 1"}], "circle"),
    ([{"name": "a", "type": "combined"}], "cannot measure"),
    ([{"name": "a", "expression": "import_os("}], "not valid Python"),
])
def test_bad_variables_are_refused(specs, message):
    with pytest.raises(ValueError, match=message):
        check_variables(specs)


def test_a_response_naming_a_missing_variable_is_refused_before_the_run():
    with pytest.raises(ValueError, match="There is no variable 'nope'"):
        check_responses(_scenario(objective={"type": "variable", "variable": "nope"}))
    with pytest.raises(ValueError, match="There is no variable 'nope'"):
        check_responses(_scenario(objective={"type": "combined", "terms": [{"type": "variable", "variable": "nope"}]}))
    check_responses(_scenario(objective={"type": "variable", "variable": "twice"}))


@pytest.mark.parametrize("bound, sign", [("at_most", 1.0), ("at_least", -1.0)])
def test_a_variable_as_a_constraint_is_normalised_by_its_limit(bound, sign):
    scenario = _scenario()
    engine, problem = _engine(scenario)
    cls, values = resolve_response({"type": "variable", "variable": "s", "limit": 4.0, "bound": bound},
                                   CONSTRAINT_ROLE)
    response = cls()
    response.role = CONSTRAINT_ROLE
    response.setup(engine, problem, values)
    state = engine.solve(np.full(problem.shape, 0.5))
    result = response.evaluate(state)
    s = result.reported["var:s"]
    assert result.value == pytest.approx(sign * (s / 4.0 - 1.0))


def test_variables_are_saved_with_the_scenario_and_old_fingerprints_stay(tmp_path):
    plain = get_run("MBB Beam").scenario
    assert "variables" not in files.to_dict(plain)            # historical fingerprints unchanged
    scenario = _scenario()
    loaded = files.load(files.save(scenario, tmp_path / "s.json"), "scenario")
    assert loaded.variables == VARIABLES
    assert files.fingerprint(loaded) != files.fingerprint(plain)


def test_a_run_records_its_variables_and_minimises_a_derived_one():
    run = get_run("MBB Beam").updated(method="q4+conlin", max_iter=5, tol=0.0)
    run = replace(run, scenario=_scenario(objective={"type": "variable", "variable": "ratio"},
                                          constraints=[{"type": "variable", "variable": "s", "limit": 50.0}]))
    method = initialized_method(run)
    history = []
    for i in range(5):
        method.step(i + 1)
        history.append(method.get_responses())
    assert {"var:s", "var:ratio", "var:twice"} <= set(history[-1])
    assert history[-1][OBJECTIVE] < history[0][OBJECTIVE]
    assert history[-1]["var:twice"] == pytest.approx(2 * history[-1]["var:ratio"])
