"""Circular-cavity physics, upwind fronts, source nucleation and feasible benchmarks."""

from dataclasses import replace

import numpy as np
import pytest

from toporia.checks.common import iterate
from toporia.checks.method import check_method
from toporia.engine.loop import initialized_method
from toporia.framework import EdgeConstraint, PointConstraint, PointSpring, Scenario
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.interpolations.simp import SIMP
from toporia.plugins.methods.levelset_hamilton_jacobi import (
    HamiltonJacobiLevelSet,
    circular_hole_matrix,
    godunov_norm,
    signed_distance,
)
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
from toporia.plugins.problems import get_run


def _method(**values):
    run = get_run("MBB Beam").updated(method=HamiltonJacobiLevelSet.name, m=0.4, **values)
    method = HamiltonJacobiLevelSet()
    method.initialize(make_problem(run.scenario, run.solver.m), run.solver)
    return method, run


def test_hamilton_jacobi_conforms():
    report = check_method(HamiltonJacobiLevelSet)
    assert report.ok, str(report)


@pytest.mark.parametrize("nu", [-0.4, 0.0, 0.3, 0.45])
@pytest.mark.parametrize("stress", [(1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 0.0, 1.0)])
def test_circular_tensor_matches_independent_stress_invariant(nu, stress):
    sx, sy, tau = stress
    # Unit E plane stress: ex=sx-nu*sy, ey=sy-nu*sx, gamma=2(1+nu)*tau.
    ex, ey, gamma = sx-nu*sy, sy-nu*sx, 2*(1+nu)*tau
    xy = np.array([[0, 0], [2.4, 0], [2.4, 0.7], [0, 0.7]])
    u = np.column_stack((ex*xy[:, 0]+0.5*gamma*xy[:, 1],
                         ey*xy[:, 1]+0.5*gamma*xy[:, 0])).ravel()
    # Kirsch limiting values: uniaxial 3, equibiaxial 4, pure shear 8.
    expected = 4*(sx*sx+sy*sy+2*tau*tau)-(sx+sy)**2
    actual = u @ circular_hole_matrix(nu, 2.4, 0.7) @ u/(2.4*0.7)
    assert actual == pytest.approx(expected, rel=2e-13)
    rigid = np.column_stack((1.2-0.3*xy[:, 1], -2.0+0.3*xy[:, 0])).ravel()
    np.testing.assert_allclose(circular_hole_matrix(nu, 2.4, 0.7) @ rigid, 0.0, atol=2e-14)


def test_cavity_derivative_matches_a_small_physical_hole_and_refines_toward_limit():
    # Uniform traction on a large plate, with a central circular void. The
    # independent FE compliance difference approaches T=3 per removed area.
    # Finite plate size and stair-stepped circle leave a few percent error;
    # this is not a finite-difference test of a SIMP density derivative.
    errors = []
    for mesh in (2.0, 4.0):
        scenario = Scenario(Lx=40, Ly=40, edge_constraints=[EdgeConstraint("left", "x")],
                            point_constraints=[PointConstraint(0, 0, "y")])
        problem = make_problem(scenario, mesh)
        physics = Q4PlaneStress()
        physics.initialize(problem, {}, SIMP(1.0))
        force = np.zeros(physics.layout.ndof)
        nodal_tractions = np.full(problem.nely+1, problem.dy)
        nodal_tractions[[0, -1]] *= 0.5
        force[2*physics.layout.node_ids[:, -1]] = nodal_tractions
        physics.layout.forces = [(1.0, force)]
        density = np.ones(problem.shape)
        full = physics.solve(density).compliances[0]
        assert full == pytest.approx(1600.0, rel=1e-10)
        hole = (problem.elem_x-20)**2 + (problem.elem_y-20)**2 < 2.0**2
        density[hole] = 0.0
        perforated = physics.solve(density).compliances[0]
        removed_area = hole.sum()*problem.dx*problem.dy
        derivative = (perforated-full)/removed_area
        errors.append(abs(derivative-3.0))
    assert errors[1] < errors[0] < 0.2
    assert errors[1] < 0.15


@pytest.mark.parametrize("velocity", [-1.0, 1.0])
def test_upwind_front_moves_with_correct_sign_on_nonsquare_grid(velocity):
    dx, dy = 0.7, 1.3
    x, y = np.meshgrid(np.arange(15)*dx, np.arange(13)*dy)
    phi = 0.6*x-0.8*y+2
    norm = godunov_norm(phi, np.full(phi.shape, velocity), dx, dy)
    np.testing.assert_allclose(norm[1:-1, 1:-1], 1.0, atol=3e-15)
    updated = phi+0.1*velocity*norm
    np.testing.assert_allclose(updated[1:-1, 1:-1], (phi+0.1*velocity)[1:-1, 1:-1], atol=2e-15)


def test_signed_distance_has_correct_sign_half_cell_offset_and_exterior_void():
    solid = np.ones((15, 20), dtype=bool)
    solid[:, 10:] = False
    phi = signed_distance(solid, 2.0, 2.0)
    np.testing.assert_array_equal(phi > 0, solid)
    np.testing.assert_allclose(phi[7, 8:12], [3.0, 1.0, -1.0, -3.0])
    assert signed_distance(np.ones((9, 9), bool), 1, 1)[4, 4] == 4.5
    assert np.all(np.isfinite(signed_distance(np.zeros((9, 9), bool), 1, 1)))


def test_source_nucleates_in_flat_solid_when_pure_advection_cannot():
    method, _ = _method()
    method.phi[:] = 0.5*method.h
    velocity = np.zeros(method.problem.shape)
    forcing = np.zeros(method.problem.shape)
    forcing[2:-2, 6:-6] = -1.0
    evolved = method._evolve(velocity, forcing)
    assert np.all(np.isfinite(evolved))
    assert evolved[4, 12] < 0
    assert np.all(evolved[[0, -1], :] > 0)
    method.settings["topological_weight"] = 0.0
    np.testing.assert_array_equal(method._evolve(velocity, forcing), method.phi)


def test_augmented_lagrangian_update_uses_volume_fraction_and_controller_stays_finite():
    method, _ = _method()
    old_lag, old_penalty = method.lag, method.penalty
    error = method.density.mean()-method.volume_target
    method.step(1)
    assert method.multiplier == pytest.approx(old_lag+error/old_penalty)
    assert method.lag == pytest.approx(old_lag+error/old_penalty)
    assert method.penalty == pytest.approx(old_penalty*0.9)
    method.penalty = 1e-6
    method.step(2)
    assert method.penalty == 1e-6
    assert np.all(np.isfinite(method.phi))


def test_unit_scaling_and_multiple_load_cases_preserve_normalised_evolution():
    first, run = _method()
    cases = [replace(case, weight=0.7*case.weight) for case in run.scenario.load_cases]
    cases += [replace(case, weight=3.3*case.weight) for case in run.scenario.load_cases]
    other_run = run.updated(E0=7*run.scenario.E0, Emin=7*run.scenario.Emin, load_cases=cases)
    other = HamiltonJacobiLevelSet()
    other.initialize(make_problem(other_run.scenario, other_run.solver.m), other_run.solver)
    assert other.energy_scale == pytest.approx(first.energy_scale*4/7, rel=1e-10)
    for iteration in range(1, 7):
        first.step(iteration)
        other.step(iteration)
        np.testing.assert_array_equal(other.density, first.density)
        np.testing.assert_allclose(other.phi, first.phi, rtol=0, atol=1e-7)


@pytest.mark.parametrize("mesh", [0.4, 1.0])
def test_mbb_converges_feasibly_and_competes_with_oc_on_the_same_mesh(mesh):
    run = get_run("MBB Beam").updated(method=HamiltonJacobiLevelSet.name, m=mesh, tol=0, max_iter=200)
    method = initialized_method(run)
    for iteration in range(1, 201):
        method.step(iteration)
        if method.is_converged():
            break
    assert method.is_converged(), method.get_responses()
    assert method.get_density().mean() <= run.scenario.volfrac+1e-12
    assert set(np.unique(method.density)) <= {0.0, 1.0}
    np.testing.assert_array_equal(method.density[method.solid], 1.0)
    check = method.physics.solve(method.density)
    assert method.get_responses()["objective"] == pytest.approx(np.dot(check.weights, check.compliances))
    reference = initialized_method(run.updated(method="q4+oc"))
    iterate(reference, 200)
    assert method.get_responses()["objective"] <= 1.1*reference.get_responses()["objective"]


def test_volume_quantisation_forced_regions_and_support_cells_are_explicit():
    method, run = _method(volfrac=0.503)
    assert method.volume_target <= run.scenario.volfrac
    assert method.volume_target == 96/192
    problem = method.problem
    problem.void_elements[2:4, 8:10] = True
    problem.passive_elements[5:7, 4:6] = True
    method.initialize(problem, run.solver)
    for iteration in range(1, 6):
        method.step(iteration)
        np.testing.assert_array_equal(method.density[problem.void_elements], 0.0)
        np.testing.assert_array_equal(method.density[method.solid], 1.0)
    problem.void_elements[-1, 0] = True  # applied-force footprint
    with pytest.raises(ValueError, match="force-bearing"):
        method.initialize(problem, run.solver)


@pytest.mark.parametrize("values,reason", [
    ({"Lz": 2.0}, "2-D"),
    ({"objective": {"type": "thermal_compliance"}}, "cannot minimise"),
    ({"constraints": [{"type": "stress", "limit": 1.0}]}, "cannot enforce"),
    ({"point_springs": [PointSpring(0, 0, 0.1)]}, "point springs"),
    ({"volfrac": 0.001}, "mandatory solid"),
])
def test_unsupported_scenarios_are_rejected(values, reason):
    run = get_run("MBB Beam").updated(method=HamiltonJacobiLevelSet.name, m=0.4, **values)
    with pytest.raises(ValueError, match=reason):
        HamiltonJacobiLevelSet().initialize(make_problem(run.scenario, run.solver.m), run.solver)
