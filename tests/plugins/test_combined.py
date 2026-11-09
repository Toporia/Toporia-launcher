"""test_combined.py — one objective made of several variables (To do item 4).

The terms are ordinary responses; the combination is a weighted sum, a smooth worst
case (KS) or a Python formula.  Its gradient must be exact for every rule, a bad spec
must be refused before the run, and a short run must lower the combined value.
"""

from dataclasses import replace

import numpy as np
import pytest

from toporia_core.checks.common import gradient_check
from toporia_core.checks.report import Report
from toporia_core.engine.loop import initialized_method
from toporia_core.framework.parts.method import OBJECTIVE
from toporia_core.framework.problem.mesh import make_problem
from toporia_core.framework.registries import OBJECTIVE_ROLE, resolve_response
from toporia_library.models.q4 import Q4Model
from toporia_library.problems import get_run
from toporia_library.responses.combined import compile_expression, term_names

TERMS = [{"type": "compliance", "weight": 1.0}, {"type": "peak_stress", "weight": 0.5, "p": 6.0},
         {"type": "volume", "weight": 0.2, "sense": "max"}]


def _setup(spec):
    run = get_run("MBB Beam")
    problem = make_problem(run.scenario, 2)
    engine = Q4Model.physics()
    engine.initialize(problem, {name: p.default for name, p in ((p.name, p) for p in Q4Model.params)})
    cls, values = resolve_response(spec, OBJECTIVE_ROLE)
    response = cls()
    response.setup(engine, problem, values)
    density = np.random.default_rng(3).uniform(0.3, 0.9, problem.shape)
    return response, engine, density


@pytest.mark.parametrize("combine", ["sum", "minmax", "expression"])
def test_the_gradient_is_exact_for_every_rule(combine):
    spec = {"type": "combined", "combine": combine, "terms": TERMS, "ks_p": 8.0,
            "expression": "compliance * peak_stress / (1 + volume)"}
    response, engine, density = _setup(spec)
    response.evaluate(engine.solve(density))           # fixes the reference values
    result = response.evaluate(engine.solve(density))
    report = Report("combined")
    gradient_check(lambda d: response.evaluate(engine.solve(d), gradient=False).value,
                   result.gradient, density, np.ones(density.shape, bool), report, "gradient")
    report.assert_ok()


def test_the_rules_combine_the_normalised_terms_as_stated():
    response, engine, density = _setup({"type": "combined", "combine": "sum", "terms": TERMS})
    state = engine.solve(density)
    first = response.evaluate(state, gradient=False)
    assert first.value == pytest.approx(1.0 + 0.5 - 0.2)          # each term is 1 at the first design
    assert set(first.reported) >= {"term:compliance", "term:peak_stress", "term:volume", "max_stress"}

    worst, *_ = _setup({"type": "combined", "combine": "minmax", "ks_p": 200.0, "terms": TERMS})
    assert worst.evaluate(state, gradient=False).value == pytest.approx(1.0, abs=np.log(3) / 200 + 1e-12)


def test_term_names_and_the_expression_are_checked():
    assert term_names([{"type": "volume"}, {"type": "volume"}, {"type": "compliance", "name": "c"}]) == [
        "volume", "volume_2", "c"]
    assert compile_expression("a * sqrt(b) + max(a, 2)", ["a", "b"])({"a": 3.0, "b": 4.0}) == 9.0
    for bad, message in [("a +", "not valid Python"), ("__import__('os')", "may call only"),
                         ("a.real", "may not use"), ("c", "not a variable here"), ("'x'", "only hold numbers")]:
        with pytest.raises(ValueError, match=message):
            compile_expression(bad, ["a", "b"])


@pytest.mark.parametrize("spec, message", [
    ({"terms": []}, "at least one term"),
    ({"terms": [{"weight": 1}]}, "needs a 'type'"),
    ({"terms": [{"type": "combined"}]}, "cannot contain another"),
    ({"terms": [{"type": "volume", "sense": "up"}]}, "'min' or 'max'"),
    ({"terms": [{"type": "volume", "name": "two words"}]}, "Python name"),
    ({"terms": [{"type": "stress"}]}, "cannot be used as the objective"),
    ({"terms": [{"type": "volume"}], "combine": "expression"}, "needs an expression"),
])
def test_a_bad_combination_is_refused_before_the_run(spec, message):
    with pytest.raises(ValueError, match=message):
        resolve_response({"type": "combined", **spec}, OBJECTIVE_ROLE)


def test_a_term_the_physics_cannot_compute_is_refused():
    run = get_run("Heat Sink").updated(method="q4_heat+mma")
    run = replace(run, scenario=replace(run.scenario, objective={
        "type": "combined", "terms": [{"type": "thermal_compliance"}, {"type": "compliance"}]}))
    with pytest.raises(ValueError, match="cannot be computed"):
        initialized_method(run)


def test_a_short_run_lowers_the_combined_objective():
    run = get_run("MBB Beam").updated(method="q4+mma", max_iter=8, tol=0.0)
    run = replace(run, scenario=replace(run.scenario, objective={
        "type": "combined", "combine": "sum",
        "terms": [{"type": "compliance"}, {"type": "peak_stress", "weight": 0.3}]}))
    method = initialized_method(run)
    values = []
    for i in range(8):
        method.step(i + 1)
        values.append(method.get_responses()[OBJECTIVE])
    assert values[-1] < values[0]
