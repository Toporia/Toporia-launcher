"""Independent diffuse-interface physics, exact derivatives and composed optimisation."""

from dataclasses import replace

import numpy as np
import pytest

from toporia.checks.response import check_response
from toporia.engine.loop import initialized_method
from toporia.framework import LoadCase, Scenario, read_param
from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.interpolations.simp import SIMP
from toporia.plugins.methods import method_class
from toporia.plugins.physics.h8_solid import H8Solid
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
from toporia.plugins.problems import get_run
from toporia.plugins.responses.phase_field import (
    PhaseFieldCompliance,
    phase_energy,
    physical_laplacian,
)


def _response(dim=2, **settings):
    problem = make_problem(Scenario(Lx=8.0, Ly=6.0, Lz=4.0 if dim == 3 else 0.0), 0.5)
    physics = H8Solid() if dim == 3 else Q4PlaneStress()
    physics.initialize(problem, {}, SIMP(3.0))
    response = PhaseFieldCompliance()
    response.setup(physics, problem, resolve_params("phase_field", response.params, settings))
    return response, physics, problem


def test_phase_field_conforms_on_all_supported_physics():
    report = check_response(PhaseFieldCompliance)
    assert report.ok, str(report)


@pytest.mark.parametrize("shape,spacing", [((4, 5), (0.7, 1.3)), ((3, 4, 5), (1.1, 0.7, 1.3))])
def test_finite_volume_energy_matches_independent_face_sum_and_exact_gradient(shape, spacing):
    rho = np.random.default_rng(14).uniform(0.1, 0.9, shape)
    epsilon = 1.2
    laplacian = physical_laplacian(shape, spacing)
    value, gradient = phase_energy(rho, laplacian, epsilon)
    # Independent physical face integral: no use of the assembled matrix.
    gradient_sum = sum(np.sum(np.diff(rho, axis=axis)**2)/h**2 for axis, h in enumerate(spacing))
    expected = (epsilon*gradient_sum/2 + np.sum(rho**2*(1-rho)**2)/epsilon)/rho.size
    assert value == pytest.approx(expected, rel=1e-14)
    fd = np.empty(shape)
    for index in np.ndindex(shape):
        plus, minus = rho.copy(), rho.copy()
        plus[index] += 1e-6
        minus[index] -= 1e-6
        fd[index] = (phase_energy(plus, laplacian, epsilon, False)[0]
                     - phase_energy(minus, laplacian, epsilon, False)[0])/2e-6
    np.testing.assert_allclose(gradient, fd, rtol=1e-6, atol=2e-10)
    np.testing.assert_allclose(laplacian @ np.ones(rho.size), 0, atol=3e-15)
    np.testing.assert_array_equal(laplacian.toarray(), laplacian.T.toarray())


@pytest.mark.parametrize("epsilon", [0.5, 1.5])
def test_resolved_planar_interface_has_correct_width_independent_surface_energy(epsilon):
    n = 800
    length = 40*epsilon
    h = length/n
    x = (np.arange(n)+0.5)*h-length/2
    rho = (0.5+0.5*np.tanh(x/(np.sqrt(2)*epsilon)))[None, :]
    energy, _ = phase_energy(rho, physical_laplacian(rho.shape, (1.0, h)), epsilon)
    integral = energy*length
    assert integral == pytest.approx(np.sqrt(2)/6, rel=2e-4)
    # 10%-90% analytic transition width = sqrt(2)*epsilon*log(9).
    width = x[np.searchsorted(rho[0], 0.9)]-x[np.searchsorted(rho[0], 0.1)]
    assert width == pytest.approx(np.sqrt(2)*epsilon*np.log(9), abs=2*h)


def test_equilibrium_interface_chemical_potential_converges_quadratically():
    errors = []
    for h in (0.1, 0.05):
        n = round(20/h)
        x = (np.arange(n)+0.5)*h-10
        rho = (0.5+0.5*np.tanh(x/np.sqrt(2)))[None, :]
        _, gradient = phase_energy(rho, physical_laplacian(rho.shape, (1.0, h)), 1.0)
        errors.append(float(np.max(np.abs(gradient[0, 10:-10])))*rho.size)
    assert errors[1] < 0.27*errors[0]


@pytest.mark.parametrize("density,expected", [(0.0, 0.0), (0.5, 0.0625), (1.0, 0.0)])
def test_pure_phases_and_constant_mixed_phase_have_no_interface_term(density, expected):
    rho = np.full((3, 4), density)
    value, gradient = phase_energy(rho, physical_laplacian(rho.shape, (0.7, 1.2)), 1.0)
    assert value == pytest.approx(expected, abs=1e-15)
    np.testing.assert_allclose(gradient, 0, atol=1e-15)


@pytest.mark.parametrize("dim", [2, 3])
def test_coupled_compliance_and_interface_gradient_and_reporting(dim):
    response, physics, problem = _response(dim)
    rng = np.random.default_rng(9)
    rho = rng.uniform(0.3, 0.85, problem.shape)
    state = physics.solve(rho)
    value = response.evaluate(state)
    assert value.value == pytest.approx(sum(value.reported.values()))
    assert response.evaluate(state, False).value == value.value
    assert response.evaluate(state, False).gradient is None
    for _ in range(5):
        direction = rng.uniform(-1, 1, problem.shape)
        plus = response.evaluate(physics.solve(rho+1e-6*direction), False).value
        minus = response.evaluate(physics.solve(rho-1e-6*direction), False).value
        assert np.sum(value.gradient*direction) == pytest.approx((plus-minus)/2e-6, rel=2e-6, abs=2e-7)
    assert response.evaluate(physics.solve(problem.upper_bound)).value == pytest.approx(1.0, abs=1e-13)


def test_zero_weight_recovers_normalised_compliance_with_fixed_reference():
    response, physics, problem = _response(perimeter_weight=0.0)
    reference = response.reference_compliance
    state = physics.solve(np.full(problem.shape, 0.4))
    result = response.evaluate(state)
    ordinary = response.compliance.evaluate(state)
    assert result.value == ordinary.value/reference
    np.testing.assert_allclose(result.gradient, ordinary.gradient/reference, rtol=1e-14)
    response.evaluate(physics.solve(np.full(problem.shape, 0.7)))
    assert response.reference_compliance == reference


def test_objective_is_invariant_to_proportional_material_and_load_case_scaling():
    response, physics, problem = _response()
    cases = [replace(case, weight=4*case.weight) for case in problem.scenario.load_cases]
    other_scenario = replace(problem.scenario, E0=7*problem.scenario.E0,
                             Emin=7*problem.scenario.Emin, load_cases=cases)
    other_problem = make_problem(other_scenario, 0.5)
    other_physics = Q4PlaneStress()
    other_physics.initialize(other_problem, {}, SIMP(3.0))
    other_response = PhaseFieldCompliance()
    other_response.setup(other_physics, other_problem, dict(response.settings))
    rho = np.random.default_rng(5).uniform(0.2, 0.9, problem.shape)
    first = response.evaluate(physics.solve(rho))
    second = other_response.evaluate(other_physics.solve(rho))
    assert other_response.reference_compliance == pytest.approx(response.reference_compliance*4/7, rel=1e-10)
    assert second.value == pytest.approx(first.value, rel=1e-10)
    np.testing.assert_allclose(second.gradient, first.gradient, rtol=1e-9, atol=1e-10)


def test_only_compatible_gradient_methods_offer_the_new_objective_and_paths_work():
    assert "phase_field" in method_class("q4+mma").capabilities.objectives
    assert "phase_field" in method_class("h8+mma").capabilities.objectives
    for name in ("q4+oc", "q4_nonlinear+mma", "q4_heat+mma", "levelset"):
        assert "phase_field" not in method_class(name).capabilities.objectives
    run = get_run("MBB Beam").updated(method="q4+mma", objective={"type": "phase_field"})
    changed = run.updated(**{"objective.interface_width": 2.5})
    assert read_param(changed, "objective.interface_width") == 2.5


def test_resolved_coarse_mbb_energy_improves_under_the_volume_budget():
    run = get_run("MBB Beam").updated(method="q4+mma", m=0.4, filter_specs=[],
                                     objective={"type": "phase_field", "interface_width": 2.5},
                                     method_params={"move": 0.1}, tol=0)
    method = initialized_method(run)
    method.step(1)
    initial = method.get_responses()["objective"]
    for iteration in range(2, 151):
        method.step(iteration)
    reported = method.get_responses()
    assert reported["volume"] <= 0.5+1e-6
    assert reported["objective"] < 0.7*initial
    assert reported["objective"] == pytest.approx(reported["normalised_compliance"]+reported["phase_energy"])
    assert np.all((method.get_density() >= 0) & (method.get_density() <= 1))
    assert np.isfinite(reported["compliance"])


def test_three_dimensional_composition_runs_with_its_native_volume_constraint():
    run = get_run("MBB Beam").updated(Lx=8.0, Ly=6.0, Lz=4.0, m=0.5,
                                     method="h8+mma", filter_specs=[], objective={"type": "phase_field"})
    method = initialized_method(run)
    for iteration in range(1, 6):
        method.step(iteration)
    assert method.get_density().shape == (2, 3, 4)
    assert method.get_responses()["volume"] <= 0.5+1e-6
    assert np.isfinite(method.get_responses()["objective"])


def test_invalid_geometry_lengths_and_zero_reference_are_rejected():
    with pytest.raises(ValueError, match="spacing"):
        physical_laplacian((2, 3), (1.0,))
    with pytest.raises(ValueError, match="positive"):
        physical_laplacian((2, 3), (1.0, 0.0))
    with pytest.raises(ValueError, match="positive"):
        phase_energy(np.ones((2, 3)), physical_laplacian((2, 3), (1, 1)), 0.0)
    problem = make_problem(Scenario(Lx=8, Ly=6, load_cases=[LoadCase(Fmag=0)]), 0.5)
    physics = Q4PlaneStress()
    physics.initialize(problem, {}, SIMP(3))
    with pytest.raises(ValueError, match="positive full-material compliance"):
        PhaseFieldCompliance().setup(physics, problem, resolve_params("phase_field", PhaseFieldCompliance.params, {}))
