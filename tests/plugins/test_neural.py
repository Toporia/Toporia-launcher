"""Coordinate-network derivatives and integration with physical responses."""

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.engine.pipeline import solver_problems
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.methods import method_class
from toporia.plugins.problems import get_run
from toporia.plugins.representations.neural import NeuralField


def field(depth=2, three_d=False, mesh=0.2):
    run = get_run("Cantilever").updated(m=mesh, Lz=10 if three_d else 0, point_loads=[])
    representation = NeuralField(width=4, depth=depth, seed=5)
    representation.setup(make_problem(run.scenario, mesh))
    return representation


def test_conformance():
    conformance(NeuralField).assert_ok()


@pytest.mark.parametrize("depth", [1, 2, 4])
@pytest.mark.parametrize("three_d", [False, True])
def test_all_weights_and_biases_have_correct_reverse_derivatives(depth, three_d):
    rep = field(depth, three_d)
    rng = np.random.default_rng(10)
    z = rep.initial() + rng.normal(0, 0.12, rep.initial().size)
    weights = rng.normal(size=rep.problem.shape)
    actual = rep.backward(z, weights)
    numerical = np.zeros_like(z)
    for index in range(z.size):
        step = np.zeros_like(z)
        step[index] = 1e-6
        numerical[index] = np.sum(weights * (rep.density(z + step) - rep.density(z - step))) / 2e-6
    np.testing.assert_allclose(actual, numerical, rtol=2e-5, atol=3e-9)


def test_uniform_start_bounds_determinism_and_mesh_independent_parameters():
    first, second, refined = field(), field(), field(mesh=0.4)
    np.testing.assert_array_equal(first.initial(), second.initial())
    np.testing.assert_array_equal(first.initial(), refined.initial())
    assert np.allclose(first.density(first.initial()), first.problem.scenario.volfrac)
    lo, hi = first.bounds()
    assert np.all((lo <= first.initial()) & (first.initial() <= hi))
    assert np.all(first.backward(first.initial(), np.ones(first.problem.shape))[:12] == 0)
    for z in (lo, hi):
        rho = first.density(z)
        assert np.isfinite(rho).all() and rho.min() >= 0 and rho.max() <= 1


@pytest.mark.parametrize("kwargs", [{"width": 1}, {"depth": 1.5}, {"seed": -1}, {"weight_bound": np.nan}])
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        NeuralField(**kwargs)


@pytest.mark.parametrize("updater", ["oc", "beso", "simpl"])
def test_element_updaters_are_refused_before_running(updater):
    run = get_run("MBB Beam").updated(method=f"q4+{updater}", representation={"type": "neural"})
    assert solver_problems(method_class(run.solver.method), run)


def test_filtered_compliance_and_volume_gradients_through_the_network():
    run = get_run("Cantilever").updated(m=0.2, method="q4+mma", point_loads=[],
                                       representation={"type": "neural", "width": 4})
    method = initialized_method(run)
    model = method._model
    z = model.initial_design() + np.random.default_rng(2).normal(0, .05, model.initial_design().size)
    direction = np.random.default_rng(3).normal(size=z.size)
    direction /= np.linalg.norm(direction)
    actual = model.evaluate(z)
    plus, minus = model.evaluate(z + 1e-4 * direction), model.evaluate(z - 1e-4 * direction)
    assert (plus.objective - minus.objective) / 2e-4 == pytest.approx(actual.objective_gradient @ direction, rel=2e-6)
    assert (plus.volume - minus.volume) / 2e-4 == pytest.approx(actual.volume_gradient @ direction, rel=2e-6)
