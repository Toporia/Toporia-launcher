"""Independent tensor checks, implicit PDE, nucleation and constrained FE runs."""

from dataclasses import replace

import numpy as np
import pytest

from toporia.checks.method import check_method
from toporia.engine.loop import initialized_method
from toporia.framework import PointSpring
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.methods.levelset_reaction_diffusion import (
    ReactionDiffusionLevelSet,
    material_fraction,
    topological_matrix,
)
from toporia.plugins.problems import get_run


def _method(**values):
    run = get_run("MBB Beam").updated(method=ReactionDiffusionLevelSet.name, m=0.4, **values)
    method = ReactionDiffusionLevelSet()
    method.initialize(make_problem(run.scenario, run.solver.m), run.solver)
    return method, run


def test_whole_method_conforms():
    report = check_method(ReactionDiffusionLevelSet)
    assert report.ok, str(report)


@pytest.mark.parametrize("nu", [-0.4, 0.0, 0.3, 0.45])
def test_tensor_matches_independent_strain_contraction_on_rectangles(nu):
    dx, dy = 2.4, 0.7
    matrix = topological_matrix(nu, dx, dy)
    # Affine displacement: engineering strain (a, d, b+c).
    a, b, c, d = 0.17, -0.12, 0.26, -0.08
    xy = np.array([[0, 0], [dx, 0], [dx, dy], [0, dy]])
    displacement = np.column_stack((a*xy[:, 0] + b*xy[:, 1],
                                    c*xy[:, 0] + d*xy[:, 1])).ravel()
    factor = 3*(1-nu)/(2*(1+nu)*(7-5*nu))
    a1 = -factor*(1-14*nu+15*nu**2)/(1-2*nu)**2
    a2 = 5*factor
    expected = dx*dy*(a1*(a+d)**2 + 2*a2*(a*a+d*d) + a2*(b+c)**2)
    assert displacement @ matrix @ displacement == pytest.approx(expected, rel=1e-13)
    # Translation and rigid rotation have no strain or topological benefit.
    rigid = np.column_stack((1.3-0.4*xy[:, 1], -2.1+0.4*xy[:, 0])).ravel()
    np.testing.assert_allclose(matrix @ rigid, 0.0, atol=2e-14)


def test_tensor_is_not_the_density_energy_matrix():
    from toporia.plugins.physics.q4_plane_stress import element_stiffness
    td = topological_matrix(0.3, 1.0, 1.0)
    ordinary = element_stiffness(0.3)
    ratio = np.vdot(td, ordinary)/np.vdot(ordinary, ordinary)
    assert np.linalg.norm(td-ratio*ordinary) > 0.01
    with pytest.raises(ValueError, match="Poisson"):
        topological_matrix(0.5, 1, 1)


def test_heaviside_is_bounded_and_has_flat_ends():
    np.testing.assert_array_equal(material_fraction(np.array([-1.0, -0.1, 0, 0.1, 1.0]), 0.1),
                                  [0, 0, 0.5, 1, 1])
    x = np.linspace(-0.2, 0.2, 101)
    assert np.all(np.diff(material_fraction(x, 0.1)) >= 0)


def test_implicit_diffusion_matches_neumann_eigenmode_and_preserves_mass():
    method, _ = _method(method_params={"dt": 0.2, "diffusion_length": 1.7})
    p = method.problem
    # One cell-centred cosine is an exact eigenvector of the no-flux FV matrix.
    mode = np.broadcast_to(np.cos(np.pi*(np.arange(p.nelx)+0.5)/p.nelx), p.shape)
    eigenvalue = 4*np.sin(np.pi/(2*p.nelx))**2/p.dx**2
    rhs = 0.3 + 0.2*mode.ravel()
    solution = method.lu.solve(rhs)
    expected = 0.3 + 0.2*mode.ravel()/(1+method.dt*1.7**2*eigenvalue)
    np.testing.assert_allclose(solution, expected, atol=3e-16)
    assert solution.mean() == pytest.approx(rhs.mean(), abs=1e-15)
    np.testing.assert_allclose(method.operator @ solution, rhs, atol=3e-16)


def test_all_domain_reaction_nucleates_an_interior_hole_from_solid():
    method, _ = _method(method_params={"diffusion_length": 0.0})
    forcing = np.full(method.problem.shape, 2.0)
    forcing[2:-2, 6:-6] = 0.0
    assert np.all(method.phi == 1.0)  # there was no initial zero contour
    for _ in range(3):
        phi, _ = method._evolve(forcing, 0.7)
        method.phi = phi.reshape(method.problem.shape)
    phi = method.phi
    assert phi[4, 12] < -method.width
    assert np.all(phi[[0, -1], :] > 0.0)  # a closed zero contour surrounds the new hole
    assert np.all(material_fraction(phi[[0, -1], :], method.width) > 0.9)
    assert method._density(phi.ravel()).mean() <= 0.7 + 1e-14


@pytest.mark.parametrize("target", [0.0, 0.13, 0.5, 1.0])
def test_multiplier_enforces_updated_volume_even_with_clipping(target):
    method, _ = _method()
    rng = np.random.default_rng(12)
    method.phi[:] = rng.uniform(-1, 1, method.phi.shape)
    phi, _ = method._evolve(rng.uniform(0, 4, method.phi.shape), target)
    assert np.min(phi) >= -1 and np.max(phi) <= 1
    assert method._density(phi).mean() == pytest.approx(target, abs=1e-14)


def test_fixed_regions_are_dirichlet_values_and_part_of_volume_budget():
    method, _ = _method()
    problem = method.problem
    problem.passive_elements[0, :3] = True
    problem.void_elements[-1, :3] = True
    method.initialize(problem, method_run_solver())
    for iteration in range(1, 4):
        method.step(iteration)
        np.testing.assert_array_equal(method.phi[0, :3], 1.0)
        np.testing.assert_array_equal(method.phi[-1, :3], -1.0)
        np.testing.assert_array_equal(method.density[0, :3], 1.0)
        np.testing.assert_array_equal(method.density[-1, :3], 0.0)
        assert method.density.mean() == pytest.approx(0.5, abs=1e-14)
    problem.passive_elements[:] = True
    problem.void_elements[:] = False
    with pytest.raises(ValueError, match="unreachable"):
        method.initialize(problem, method_run_solver())


def method_run_solver():
    return get_run("MBB Beam").updated(method=ReactionDiffusionLevelSet.name,
                                       method_params={"nrelax": 0}).solver


def test_load_scaling_cancels_from_evolution_and_multicase_weights_are_respected():
    first, run = _method()
    cases = run.scenario.load_cases
    second_cases = [replace(case, weight=0.3*case.weight) for case in cases]
    # Duplicate the same load with weights summing to four, i.e. doubled force.
    second_cases += [replace(case, weight=3.7*case.weight) for case in cases]
    other_run = run.updated(load_cases=second_cases)
    other = ReactionDiffusionLevelSet()
    other.initialize(make_problem(other_run.scenario, other_run.solver.m), other_run.solver)
    np.testing.assert_allclose(other.topological_benefit(), 4*first.topological_benefit(), rtol=1e-12)
    assert other.get_responses()["objective"] == pytest.approx(4*first.get_responses()["objective"])
    first.step(1)
    other.step(1)
    np.testing.assert_allclose(first.phi, other.phi, atol=1e-13)


def test_mbb_reaches_volume_reports_same_design_and_keeps_supplied_mesh():
    method, _ = _method()
    initial = method.get_responses()["objective"]
    for iteration in range(1, 61):
        assert method.continuing() == (iteration <= 30)
        method.step(iteration)
        expected = 1 - 0.5*min(iteration/30, 1)
        assert method.density.mean() == pytest.approx(expected, abs=1e-14)
    assert method.problem.shape == (8, 24)
    assert method.get_responses()["objective"] < 2.2*initial
    state = method.physics.solve(method.get_density())
    assert method.get_responses()["objective"] == pytest.approx(np.dot(state.weights, state.compliances))
    assert np.any(method.phi < -method.width) and np.any(method.phi > method.width)


def test_material_units_cancel_from_normalised_evolution():
    first, run = _method()
    other_run = run.updated(E0=7*run.scenario.E0, Emin=7*run.scenario.Emin)
    other = ReactionDiffusionLevelSet()
    other.initialize(make_problem(other_run.scenario, other_run.solver.m), other_run.solver)
    # Displacement solves accumulate round-off through the beam's condition number.
    np.testing.assert_allclose(other.topological_benefit(), first.topological_benefit()/7,
                               rtol=1e-9, atol=1e-12)
    first.step(1)
    other.step(1)
    np.testing.assert_allclose(other.phi, first.phi, rtol=0, atol=2e-10)


def test_available_material_below_budget_is_feasible_and_all_fixed_mesh_works():
    method, run = _method()
    problem = method.problem
    problem.void_elements[2:-2, :] = True
    problem.void_elements[:, 6:-6] = True
    # Keep a positive-definite ersatz FE system, even with this severe mask.
    method.initialize(problem, run.solver)
    assert method.target == pytest.approx(problem.upper_bound.mean())
    method.step(1)
    assert method.density.mean() <= run.scenario.volfrac
    run = run.updated(volfrac=1.0)
    problem = make_problem(run.scenario, run.solver.m)
    problem.passive_elements[:] = True
    method.initialize(problem, run.solver)
    method.step(1)
    np.testing.assert_array_equal(method.phi, 1.0)
    assert method.change == 0 and method.density.mean() == 1.0


@pytest.mark.parametrize("values,reason", [
    ({"Lz": 2.0}, "2-D"),
    ({"objective": {"type": "thermal_compliance"}}, "cannot minimise"),
    ({"constraints": [{"type": "stress", "limit": 1.0}]}, "cannot enforce"),
    ({"point_springs": [PointSpring(0, 0, 0.1)]}, "point springs"),
])
def test_incompatible_scenarios_are_rejected_even_on_direct_initialize(values, reason):
    run = get_run("MBB Beam").updated(method=ReactionDiffusionLevelSet.name, m=0.2, **values)
    with pytest.raises(ValueError, match=reason):
        ReactionDiffusionLevelSet().initialize(make_problem(run.scenario, run.solver.m), run.solver)
    with pytest.raises(ValueError):
        initialized_method(run)
