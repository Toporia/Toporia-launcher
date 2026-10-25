"""test_buckling.py — linearised buckling on the 2-D Q4 engine.

Three things are held to account: the load factor of a slender column against
Euler's formula, the sensitivity of the load factors (including the part through
the prebuckling displacements) against finite differences, and the preset
running through the engine.
"""

import importlib.util
import json
from dataclasses import replace

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single_with_store
from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario
from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.physics import q4_buckling
from toporia.plugins.physics.q4_buckling import Q4Buckling, geometric_stiffness_basis
from toporia.plugins.problems import get_run
from toporia.plugins.responses.buckling import BucklingLoad

WIDTH, LENGTH, MESH = 4.0, 40.0, 2.0


def _column():
    """A solid column lying along x: clamped at x = 0, unit compression spread over the nodes of its free end.

    The axis follows the parent Q4 engine's coordinate convention.
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
    try:
        for iteration in range(1, 5):
            method.step(iteration)
    finally:
        method.close()
    assert np.all(np.isfinite(method.get_density()))


def test_uniform_tension_has_no_positive_buckling_factor_and_a_slack_constraint():
    scenario = replace(_column().scenario, nu=0.0, load_cases=[LoadCase(Fmag=0.0, Fa=0.0)])
    problem = make_problem(scenario, 0.5)
    engine = _engine(problem)
    state = engine.solve(np.ones(problem.shape))
    # Manufactured uniform axial strain, with no local compression from end
    # restraints or concentrated nodal forces: σxx > 0, σyy = τxy = 0.
    x = np.broadcast_to(np.linspace(0, scenario.Lx, problem.nelx + 1),
                        (problem.nely + 1, problem.nelx + 1))
    state.U[2 * engine.layout.node_ids, 0] = x
    assert engine.buckling_factors(state, 0, 3).size == 0
    response = BucklingLoad()
    response.setup(engine, problem, resolve_params("buckling_load", response.params, {}))
    result = response.evaluate(state)
    assert result.value == result.exact == -1.0
    assert np.array_equal(result.gradient, np.zeros(problem.shape))


def test_material_and_load_scaling_preserve_physical_units():
    problem = _column()
    engine = _engine(problem)
    base = engine.buckling_factors(engine.solve(np.ones(problem.shape)), 0, 2)
    scenario = replace(problem.scenario, E0=7 * problem.scenario.E0, Emin=7 * problem.scenario.Emin,
                       load_cases=[replace(problem.scenario.load_cases[0], Fmag=3 * problem.scenario.load_cases[0].Fmag)])
    scaled = make_problem(scenario, MESH)
    other = _engine(scaled)
    factors = other.buckling_factors(other.solve(np.ones(scaled.shape)), 0, 2)
    assert factors == pytest.approx(base * 7 / 3, rel=1e-8)


def test_sparse_and_dense_pencils_agree_on_factors_and_sensitivities(monkeypatch):
    scenario = replace(_column().scenario, Lx=8.0, Ly=2.0, point_loads=[PointLoad(x=8.0, y=1.0)],
                       load_cases=[LoadCase(Fmag=0.1, Fa=180.0)])
    problem = make_problem(scenario, 1.0)
    engine = _engine(problem)
    density = _random_density(problem)
    monkeypatch.setattr(q4_buckling, "_DENSE_LIMIT", 10000)
    dense_state = engine.solve(density)
    dense = engine.buckling_factors(dense_state, 0, 3)
    gradient = engine.buckling_sensitivity(dense_state, 0, 0)
    monkeypatch.setattr(q4_buckling, "_DENSE_LIMIT", 0)
    sparse_state = engine.solve(density)
    assert engine.buckling_factors(sparse_state, 0, 3) == pytest.approx(dense, rel=1e-8)
    assert engine.buckling_sensitivity(sparse_state, 0, 0) == pytest.approx(gradient, rel=1e-7, abs=1e-10)


def test_small_pencil_accepts_more_requested_modes_than_free_dofs():
    scenario = Scenario(Lx=1.0, Ly=1.0,
                        edge_constraints=[EdgeConstraint(edge="left", dof="both")],
                        point_loads=[PointLoad(x=1.0, y=0.0)],
                        load_cases=[LoadCase(Fmag=0.1, Fa=180.0)])
    problem = make_problem(scenario, 1.0)
    engine = _engine(problem)
    state = engine.solve(np.ones(problem.shape))
    factors = engine.buckling_factors(state, 0, 20)
    assert factors.size <= engine.layout.free_dofs.size
    assert np.all(np.isfinite(factors)) and np.all(factors > 0)
    with pytest.raises(ValueError, match="positive integer"):
        engine.buckling_factors(state, 0, 0)


@pytest.mark.skipif(importlib.util.find_spec("pymoto") is None, reason="optional dependency: pymoto")
def test_column_optimisation_meets_both_the_buckling_and_volume_limits(tmp_path):
    run = get_run("Column Buckling").updated(m=0.3, max_iter=120, save_every=0).with_output_dir(tmp_path)
    _, density = run_single_with_store(run)
    record = json.loads((tmp_path / "run.json").read_text())
    result = record["result"]
    assert result["feasible"]
    assert density.mean() <= 0.3 * 1.01
    assert result["final"]["buckling_load"] >= 1.0
    assert result["final"]["constraint_0_buckling_load"] <= 0.01
