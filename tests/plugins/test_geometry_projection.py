"""Independent cap integrals, capsule measures, adjoints and 2D/3D integration."""

import numpy as np
import pytest
from numpy.polynomial.legendre import leggauss

from toporia.checks.representation import check_representation
from toporia.engine.loop import initialized_method
from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Run, Scenario, Solver
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.problems import get_run
from toporia.plugins.representations.geometry_projection import GeometryProjection, cap_projection


def _representation(dim=2, m=1.0, **params):
    scenario = Scenario(Lx=10.0, Ly=6.0, Lz=6.0 if dim == 3 else 0.0)
    problem = make_problem(scenario, m)
    representation = GeometryProjection(n_x=1, n_y=1, n_z=1, bar_radius=1.0, **params)
    representation.setup(problem)
    return representation, problem


def test_geometry_projection_conforms():
    report = check_representation(GeometryProjection)
    assert report.ok, str(report)


@pytest.mark.parametrize("dim", [2, 3])
def test_cap_formula_matches_independent_cross_section_quadrature(dim):
    nodes, weights = leggauss(100)
    for t in (-0.8, -0.3, 0.0, 0.4, 0.9):
        lower = -t
        x = 0.5 * (1 - lower) * nodes + 0.5 * (1 + lower)
        cross_section = 2 * np.sqrt(1 - x * x) if dim == 2 else np.pi * (1 - x * x)
        measure = np.pi if dim == 2 else 4 * np.pi / 3
        integral = 0.5 * (1 - lower) * np.dot(weights, cross_section) / measure
        value, slope = cap_projection(t, 1.0, dim)
        assert value == pytest.approx(integral, abs=3e-7)
        fd = (cap_projection(t + 1e-6, 1.0, dim)[0] - cap_projection(t - 1e-6, 1.0, dim)[0]) / 2e-6
        assert slope == pytest.approx(fd, rel=1e-8)
    values, slopes = cap_projection(np.array([-2.0, 2.0]), 1.0, dim)
    np.testing.assert_array_equal(values, [0.0, 1.0])
    np.testing.assert_array_equal(slopes, [0.0, 0.0])


@pytest.mark.parametrize("dim", [2, 3])
def test_every_endpoint_and_activation_gradient_matches_finite_differences(dim):
    representation, problem = _representation(dim)
    rng = np.random.default_rng(19)
    z = np.clip(representation.initial() + rng.uniform(-0.1, 0.1, representation.initial().size), 0.08, 0.92)
    weights = rng.normal(size=problem.shape)
    gradient = representation.backward(z, weights)
    fd = np.empty_like(z)
    for i in range(z.size):
        direction = np.zeros_like(z)
        direction[i] = 1e-6
        fd[i] = np.sum(weights * (representation.density(z + direction)
                                 - representation.density(z - direction))) / 2e-6
    np.testing.assert_allclose(gradient, fd, rtol=2e-4, atol=2e-7)


@pytest.mark.parametrize("dim,m,tolerance", [(2, 10.0, 0.005), (3, 4.0, 0.02)])
def test_single_capsule_matches_analytic_area_or_volume(dim, m, tolerance):
    representation, problem = _representation(dim, m)
    bars = representation.initial().reshape(-1, representation.per_bar)
    bars[:, -1] = 0
    a, b = np.array([3.0, 3.0, 3.0])[:dim], np.array([7.0, 3.0, 3.0])[:dim]
    bars[0] = [*(a / representation.lengths), *(b / representation.lengths), 1.0]
    cell = problem.dx * problem.dy * (problem.dz if dim == 3 else 1.0)
    measured = np.sum(representation.density(bars.ravel())) * cell
    expected = 8 + np.pi if dim == 2 else 4 * np.pi + 4 * np.pi / 3
    assert measured == pytest.approx(expected, rel=tolerance)


@pytest.mark.parametrize("dim", [2, 3])
def test_reversing_endpoints_preserves_density_and_swaps_their_gradients(dim):
    representation, problem = _representation(dim)
    bars = representation.initial().reshape(-1, representation.per_bar)
    reversed_bars = bars.copy()
    reversed_bars[:, :dim], reversed_bars[:, dim:2 * dim] = bars[:, dim:2 * dim], bars[:, :dim]
    np.testing.assert_allclose(representation.density(bars.ravel()),
                               representation.density(reversed_bars.ravel()), atol=1e-14)
    weights = np.random.default_rng(7).normal(size=problem.shape)
    gradient = representation.backward(bars.ravel(), weights).reshape(bars.shape)
    reverse_gradient = representation.backward(reversed_bars.ravel(), weights).reshape(bars.shape)
    np.testing.assert_allclose(reverse_gradient[:, :dim], gradient[:, dim:2 * dim], atol=1e-12)
    np.testing.assert_allclose(reverse_gradient[:, -1], gradient[:, -1], atol=1e-12)


def test_size_zero_removes_components_without_losing_their_size_derivative():
    representation, problem = _representation()
    bars = representation.initial().reshape(-1, representation.per_bar)
    bars[:, -1] = 0
    np.testing.assert_array_equal(representation.density(bars.ravel()), 0)
    gradient = representation.backward(bars.ravel(), np.ones(problem.shape)).reshape(bars.shape)
    np.testing.assert_array_equal(gradient[:, :-1], 0)
    assert np.all(gradient[:, -1] > 0)
    assert representation.outlines(bars.ravel()) == []


def test_collapsed_and_overlapping_segments_have_finite_subgradients():
    representation, problem = _representation()
    bars = representation.initial().reshape(-1, representation.per_bar)
    bars[:, :-1] = 0.5
    field = representation.density(bars.ravel())
    assert np.all((field >= 0) & (field <= 1))
    assert np.all(np.isfinite(representation.backward(bars.ravel(), np.ones(problem.shape))))
    for polygon in representation.outlines(bars.ravel()):
        assert polygon.shape == (73, 2)
        assert np.array_equal(polygon[0], polygon[-1])


def test_the_3d_representation_runs_through_the_existing_h8_model():
    scenario = Scenario(Lx=12.0, Ly=8.0, Lz=4.0, volfrac=0.5,
                        edge_constraints=[EdgeConstraint("left")], point_loads=[PointLoad(12.0, 4.0)],
                        load_cases=[LoadCase(1.0, 270.0)])
    solver = Solver(method="h8+mma", m=0.5, max_iter=4, tol=0.0,
                    representation={"type": "geometry_projection", "n_x": 2, "n_y": 1,
                                    "bar_radius": 1.2}, method_params={"move": 0.02}, filter_specs=[])
    method = initialized_method(Run(scenario=scenario, solver=solver))
    for iteration in range(1, 5):
        method.step(iteration)
        assert np.isfinite(method.get_responses()["objective"])
        assert np.all((method.get_density() >= 0) & (method.get_density() <= 1))
    assert method._model.representation.outlines(method.x) is None


def test_a_pure_geometric_mbb_run_uses_the_budget_and_beats_uniform_material():
    run = get_run("MBB Beam").updated(m=0.4, method="q4+mma", max_iter=150, tol=0.0,
        representation={"type": "geometry_projection"}, method_params={"move": 0.02}, filter_specs=[])
    method = initialized_method(run)
    for iteration in range(1, 151):
        method.step(iteration)
    final = method._model.evaluate(method.x, gradients=False)
    # Uniform 0.5 on this mesh has compliance 975.83; no claim of an OC-optimal layout.
    assert final.objective < 0.8 * 975.83
    assert method.get_density().mean() <= run.scenario.volfrac + 0.001


@pytest.mark.parametrize("params", [{"n_x": 0}, {"n_z": 1.5}, {"bar_radius": 0},
                                   {"projection_width": np.nan}, {"start_size": 1.1}])
def test_invalid_parameters_are_rejected(params):
    with pytest.raises(ValueError):
        GeometryProjection(**params)


def test_underresolved_stock_radius_is_rejected_with_mesh_advice():
    with pytest.raises(ValueError, match="refine the mesh"):
        _representation(m=0.2)
