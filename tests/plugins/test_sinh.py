"""SINH effective resource budget: primal, adjoint, updaters and reporting."""

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.engine.records import check_limits
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.interpolations.sinh import SINH
from toporia.plugins.problems import get_run
from toporia.plugins.responses.volume import Volume


@pytest.mark.parametrize("penal", [0., 1e-10, 1., 3., 20.])
def test_exact_paper_measures_endpoints_and_derivatives(penal):
    law = SINH(penal)
    rho = np.linspace(0, 1, 31)
    eta = law.volume_density(rho)
    assert eta[0] == 0 and eta[-1] == pytest.approx(1., abs=2e-15)
    assert np.all(eta >= rho - 1e-15) and np.all(np.diff(eta) > 0)
    expected = rho if penal < 1e-8 else 1 - np.sinh(penal * (1-rho)) / np.sinh(penal)
    np.testing.assert_allclose(eta, expected, atol=3e-15)
    np.testing.assert_allclose(law.stiffness(rho, 2., .1), .1 + 1.9*rho)
    # Complex steps avoid subtracting two values near one when p=20 makes
    # the derivative near solid only 8e-8. Full FE-chain tests below use FD.
    derivative = np.imag(law.volume_density(rho + 1e-25j)) / 1e-25
    np.testing.assert_allclose(derivative, law.volume_slope(rho), rtol=1e-12, atol=1e-13)


def test_conformance():
    conformance(SINH).assert_ok()


@pytest.mark.parametrize("three_d", [False, True])
@pytest.mark.parametrize("representation", ["element_density", "bspline", "neural"])
def test_filtered_physical_compliance_and_effective_volume_gradients(three_d, representation):
    method = initialized_method(get_run("Cantilever").updated(
        method="h8+mma" if three_d else "q4+mma", Lz=5 if three_d else 0,
        m=.2, point_loads=[], interpolation={"type": "sinh", "penal": 3.},
        representation={"type": representation}))
    model = method._model
    rng = np.random.default_rng(14)
    z = method.x.copy() + rng.normal(0, .01, method.x.shape)
    direction = rng.normal(size=z.shape)
    direction /= np.linalg.norm(direction)
    e = model.evaluate(z)
    plus, minus = model.evaluate(z+1e-4*direction), model.evaluate(z-1e-4*direction)
    assert (plus.objective-minus.objective)/2e-4 == pytest.approx(np.sum(e.objective_gradient*direction), rel=2e-5)
    assert (plus.volume-minus.volume)/2e-4 == pytest.approx(np.sum(e.volume_gradient*direction), rel=2e-6)
    assert e.volume == pytest.approx(model.volume_of(z), rel=1e-14)
    assert e.volume > model.physical(z).sum()


@pytest.mark.parametrize("updater", ["oc", "mma", "conlin", "simpl", "adam"])
def test_the_budget_and_cheap_bisection_use_effective_volume(updater):
    method = initialized_method(get_run("MBB Beam").updated(
        method=f"q4+{updater}", m=.2, interpolation={"type": "sinh"}, tol=0., max_iter=8))
    model = method._model
    assert model.volume_of(method.x) == pytest.approx(model.volume_limit, abs=1e-8)
    assert method.get_density().mean() < .3
    for iteration in range(1, 9):
        method.step(iteration)
    responses = method.get_responses()
    assert responses["effective_volume_fraction"] == pytest.approx(model.volume_of(method.x)/method.density.size)
    assert responses["geometric_volume_fraction"] == pytest.approx(method.density.mean())
    if updater != "adam":  # Adam's inequality penalty only approximates feasibility.
        assert model.volume_of(method.x) <= model.volume_limit * 1.002


def test_volume_objective_and_limit_reporting_do_not_silently_use_geometric_volume():
    run = get_run("MBB Beam").updated(m=.2, interpolation={"type": "sinh"})
    method = initialized_method(run)
    model = method._model
    rho = np.full(model.problem.shape, .4)
    state = model.engine.solve(rho)
    response = Volume()
    response.setup(model.engine, model.problem, {})
    actual = response.evaluate(state)
    assert actual.value == pytest.approx(SINH().volume_density(rho).sum())
    np.testing.assert_allclose(actual.gradient, SINH().volume_slope(rho))
    report = check_limits(run.scenario, {"volume": .4, "effective_volume_fraction": .7})
    assert report[0]["name"] == "effective volume budget" and not report[0]["satisfied"]


def test_continuation_changes_resource_cost_and_variants_delegate_cheap_volume():
    run = get_run("MBB Beam").updated(m=.2, interpolation={"type": "sinh", "penal": 1.},
                                      variants={"path": "interpolation.penal", "values": [1., 3.], "nominal": 1})
    model = initialized_method(run)._model
    z = model.initial_design()
    assert model.volume_of(z) == pytest.approx(model.evaluate(z).volume)
    single = model.models[1]
    before = single.volume_of(z)
    single.set_parameter("interpolation.penal", 5.)
    assert single.volume_of(z) > before


@pytest.mark.parametrize("penal", [-1., np.nan, np.inf, 21.])
def test_invalid_penalty(penal):
    with pytest.raises(ValueError):
        SINH(penal)


def test_sinh_initialisation_respects_passive_material_and_resource_budget():
    run = get_run("Drone Arm").updated(m=.2, interpolation={"type": "sinh"})
    method = initialized_method(run)
    problem = make_problem(run.scenario, run.solver.m)
    rho = method.get_density()
    np.testing.assert_array_equal(rho[problem.passive_elements], np.ones(np.sum(problem.passive_elements)))
    assert method._model.volume_of(method.x) <= method._model.volume_limit + 1e-8
