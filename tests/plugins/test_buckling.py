"""test_buckling.py — linearised buckling on the 2-D Q4 engine.

Three things are held to account: the load factor of a slender column against
Euler's formula, the sensitivity of the load factors (including the part through
the prebuckling displacements) against finite differences, and the preset
running through the engine.
"""

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario
from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.physics.q4_buckling import Q4Buckling, geometric_stiffness_basis
from toporia.plugins.problems import get_run
from toporia.plugins.responses.buckling import BucklingLoad

WIDTH, LENGTH, MESH = 4.0, 40.0, 2.0


def _column():
    """A solid column lying along x: clamped at x = 0, unit compression spread over the nodes of its free end.

    The column lies along x because the solver's y axis runs against the picture's (rows are
    numbered the other way), which would turn an axial load in y into tension.
    """
    nodes = int(WIDTH * MESH) + 1
    loads = [PointLoad(x=LENGTH, y=j / MESH) for j in range(nodes)]
    scenario = Scenario(Lx=LENGTH, Ly=WIDTH, point_loads=loads,
                        edge_constraints=[EdgeConstraint(edge="left", dof="both")],
                        load_cases=[LoadCase(Fmag=1.0 / nodes, Fa=180.0, weight=1.0)])
    return make_problem(scenario, MESH)


def _engine(problem, p_sigma=4.0):
    engine = Q4Buckling()
    engine.initialize(problem, resolve_params("q4_buckling", Q4Buckling.params, {"p_sigma": p_sigma}))
    return engine


def test_geometric_stiffness_matrices_are_symmetric_and_ignore_rigid_translations():
    # K_σ acts on displacement gradients, so a uniform translation must produce no force.
    basis = geometric_stiffness_basis(1.0, 1.0)
    translation = np.tile([1.0, 0.0], 4)
    for T in basis:
        assert np.allclose(T, T.T)
        assert np.allclose(T @ translation, 0.0)
        assert np.allclose(T @ np.tile([0.0, 1.0], 4), 0.0)


def test_cantilever_column_matches_euler():
    problem = _column()
    engine = _engine(problem)
    state = engine.solve(np.ones(problem.shape))
    factor = engine.buckling_factors(state, 0, 3)[0]
    euler = np.pi ** 2 * 1.0 * (WIDTH ** 3 / 12.0) / (4.0 * LENGTH ** 2)
    assert factor == pytest.approx(euler, rel=0.04), (factor, euler)


def _random_density(problem, seed=3):
    return np.random.default_rng(seed).uniform(0.3, 0.95, problem.shape)


def test_load_factor_sensitivity_matches_finite_differences_including_the_adjoint_term():
    problem = _column()
    engine = _engine(problem)
    density = _random_density(problem)
    state = engine.solve(density)
    factors = engine.buckling_factors(state, 0, 4)
    # Well-separated modes, otherwise the individual eigenvalues are not differentiable.
    assert factors[1] / factors[0] > 1.05
    gradient = engine.buckling_sensitivity(state, 0, 0)
    for flat in np.argsort(-np.abs(gradient).ravel())[:5]:
        index = np.unravel_index(flat, problem.shape)
        h = 1e-4
        plus, minus = density.copy(), density.copy()
        plus[index] += h
        minus[index] -= h
        fd = (engine.buckling_factors(engine.solve(plus), 0, 1)[0]
              - engine.buckling_factors(engine.solve(minus), 0, 1)[0]) / (2 * h)
        assert gradient[index] == pytest.approx(fd, rel=1e-4), (index, gradient[index], fd)


def test_response_gradient_matches_finite_differences():
    problem = _column()
    engine = _engine(problem)
    response = BucklingLoad()
    response.setup(engine, problem, resolve_params("buckling_load", BucklingLoad.params,
                                                   {"min_load": 0.01, "modes": 4}))
    density = _random_density(problem, seed=5)
    result = response.evaluate(engine.solve(density))
    for flat in np.argsort(-np.abs(result.gradient).ravel())[:5]:
        index = np.unravel_index(flat, problem.shape)
        h = 1e-4
        plus, minus = density.copy(), density.copy()
        plus[index] += h
        minus[index] -= h
        fd = (response.evaluate(engine.solve(plus), gradient=False).value
              - response.evaluate(engine.solve(minus), gradient=False).value) / (2 * h)
        assert result.gradient[index] == pytest.approx(fd, rel=1e-4)


def test_preset_runs_a_few_iterations():
    preset = get_run("Column Buckling")
    assert preset.solver.method.startswith("q4_buckling+")
    assert [c["type"] for c in preset.scenario.constraints] == ["buckling_load"]
    # CONLIN stands in for the preset's MMA, which needs an optional package; both take the constraint.
    run = preset.updated(method="q4_buckling+conlin", m=0.5, max_iter=4, save_every=0)
    method = initialized_method(run)
    for iteration in range(1, 5):
        method.step(iteration)
    assert np.all(np.isfinite(method.get_density()))
