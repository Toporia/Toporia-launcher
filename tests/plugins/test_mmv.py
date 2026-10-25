"""Geometry, exact adjoint and optimisation of the restricted 2-D MMV family."""

from math import gamma

import numpy as np
import pytest

from toporia.checks.representation import check_representation
from toporia.engine.loop import initialized_method
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.problems import get_run
from toporia.plugins.representations.mmc import MovingMorphableComponents
from toporia.plugins.representations.mmv import MovingMorphableVoids


def _voids(m=0.5, **params):
    run = get_run("MBB Beam").updated(m=m)
    problem = make_problem(run.scenario, run.solver.m)
    voids = MovingMorphableVoids(**params)
    voids.setup(problem)
    return voids, problem


def test_mmv_conforms():
    report = check_representation(MovingMorphableVoids)
    assert report.ok, str(report)


def test_holes_are_the_geometric_dual_of_components_and_have_closed_boundaries():
    voids, problem = _voids(n_x=3, n_y=2)
    bars = MovingMorphableComponents(max_thickness=0.5)
    bars.setup(problem)
    z = voids.initial()
    assert z.size == 30
    assert np.all((z >= 0) & (z <= 1))
    assert np.allclose(voids.density(z) + bars.density(z), 1.0, atol=1e-15)
    for polygon in voids.outlines(z):
        assert polygon.shape == (73, 2)
        assert np.array_equal(polygon[0], polygon[-1])
    weights = np.random.default_rng(10).normal(size=problem.shape)
    assert np.allclose(voids.backward(z, weights), -bars.backward(z, weights))


@pytest.mark.parametrize("overlap", [False, True])
def test_all_geometric_derivatives_including_rotations_and_overlaps(overlap):
    voids, problem = _voids(n_x=2, n_y=1)
    rng = np.random.default_rng(11)
    z = np.clip(voids.initial() + rng.uniform(-0.03, 0.03, 10), 0.05, 0.95)
    if overlap:
        z[5:7] = z[:2] + 0.03
    weights = rng.normal(size=problem.shape)
    gradient = voids.backward(z, weights)
    fd = np.empty_like(z)
    for i in range(len(z)):
        step = np.eye(1, len(z), i).ravel() * 1e-6
        fd[i] = np.sum(weights * (voids.density(z + step) - voids.density(z - step))) / 2e-6
    np.testing.assert_allclose(gradient, fd, rtol=2e-5, atol=2e-6)


def test_saturated_overlapping_voids_have_finite_gradients_without_division():
    voids, problem = _voids(m=2.0, n_x=2, n_y=1)
    z = voids.initial().reshape(-1, 5)
    z[:, :2] = 0.5
    z[:, 2:4] = 1.0
    voids.set_parameter("edge_width", 0.1)
    density = voids.density(z.ravel())
    assert density.min() == 0.0
    assert np.all(np.isfinite(voids.backward(z.ravel(), np.ones(problem.shape))))


def test_enlarging_a_hole_removes_material():
    voids, _ = _voids(n_x=1, n_y=1)
    z = voids.initial()
    larger = z.copy()
    larger[2:4] += 0.05
    assert np.all(voids.density(larger) <= voids.density(z) + 1e-15)
    assert voids.density(larger).mean() < voids.density(z).mean()


def test_resolved_single_hole_matches_analytic_superellipse_area():
    voids, problem = _voids(m=4, n_x=1, n_y=1, start_size=0.2, edge_width=0.1)
    z = voids.initial()
    physical = voids.low + z * voids.span
    area = 4 * physical[2] * physical[3] * gamma(1 + 1 / 6) ** 2 / gamma(1 + 2 / 6)
    measured = np.sum(1 - voids.density(z)) * problem.dx * problem.dy
    assert measured == pytest.approx(area, rel=0.005)


@pytest.mark.parametrize("params", [{"n_x": 0}, {"n_y": 1.5}, {"start_size": 0.5},
                                   {"edge_width": 0}, {"edge_width": np.nan}])
def test_invalid_geometry_is_rejected(params):
    with pytest.raises(ValueError):
        MovingMorphableVoids(**params)


def test_mma_reaches_a_feasible_volume_and_reduces_compliance():
    run = get_run("MBB Beam").updated(
        m=0.5, method="q4+mma", representation={"type": "mmv"},
        method_params={"move": 0.02}, max_iter=60, tol=0.0, save_every=0,
    )
    method = initialized_method(run)
    objectives = []
    for iteration in range(1, 61):
        method.step(iteration)
        objectives.append(method.get_responses()["objective"])
    assert np.all(np.isfinite(objectives))
    assert objectives[-1] < 0.9 * objectives[0]
    assert method.get_density().mean() <= run.scenario.volfrac + 0.005
