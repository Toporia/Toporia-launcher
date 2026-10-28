"""Independent subcell quadrature, virtual work, supports and fine-grid checks."""

from dataclasses import replace

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.framework import HoleConfig, LoadCase, PointConstraint
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.models.q4_multiresolution import Q4MultiresolutionModel
from toporia.plugins.physics.q4_multiresolution import Q4Multiresolution
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
from toporia.plugins.problems import get_run


def engines(shape=(8, 12), factor=2, scenario=None):
    run = get_run("Cantilever").updated(Lx=shape[1], Ly=shape[0], m=1,
                                       point_loads=[], filter_specs=[])
    if scenario is not None:
        run = replace(run, scenario=scenario)
    problem = make_problem(run.scenario, run.solver.m)
    coarse, fine = Q4Multiresolution(), Q4PlaneStress()
    coarse.initialize(problem, {"coarsening": factor})
    fine.initialize(problem, {})
    return coarse, fine


def test_model_and_physics_conformance_use_the_identity_reference_mode():
    conformance(Q4MultiresolutionModel).assert_ok()
    conformance(Q4Multiresolution).assert_ok()


def test_factor_one_is_the_unchanged_q4_solve_and_gradient_path():
    multi, fine = engines(factor=1)
    density = np.random.default_rng(4).uniform(0.3, 0.9, multi.problem.shape)
    a, b = multi.solve(density), fine.solve(density)
    np.testing.assert_array_equal(a.U, b.U)
    assert a.compliances == b.compliances
    np.testing.assert_array_equal(multi.stiffness_slope(a), fine.stiffness_slope(b))
    np.testing.assert_array_equal(multi.strain_energy(a, 0), fine.strain_energy(b, 0))


@pytest.mark.parametrize("factor", [2, 3, 4])
def test_prolongation_exactly_reproduces_bilinear_fields_and_preserves_virtual_work(factor):
    multi, _ = engines((12, 12), factor)
    ny, nx = multi.analysis_shape
    y, x = np.meshgrid(np.linspace(0, 12, ny + 1), np.linspace(0, 12, nx + 1), indexing="ij")
    ux, uy = 0.7 + x - 0.4 * y + 0.02 * x * y, -0.3 + 0.2 * x + 0.6 * y
    u = np.column_stack([ux.ravel(order="F"), uy.ravel(order="F")]).ravel()
    actual = multi.prolongation @ u
    yf, xf = multi.problem.node_y, multi.problem.node_x
    expected = np.column_stack([(0.7 + xf - 0.4 * yf + 0.02 * xf * yf).ravel(order="F"),
                                (-0.3 + 0.2 * xf + 0.6 * yf).ravel(order="F")]).ravel()
    np.testing.assert_allclose(actual, expected, atol=4e-15)
    load = np.random.default_rng(3).normal(size=len(actual))
    assert load @ actual == pytest.approx((multi.prolongation.T @ load) @ u, abs=1e-12)


def independent_subcell_matrix(moduli, nu, dx_cell=1., dy_cell=1.):
    """Integrate the coarse shape gradients separately over each density cell.

    Q4's existing local order is used: global top-left, top-right, bottom-right,
    bottom-left. The parent eta coordinate follows that local convention.
    This builder does not use the implementation's prolongation or fine KE.
    """
    ny, nx = moduli.shape
    constitutive = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]]) / (1 - nu**2)
    corners = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    result = np.zeros((8, 8))
    for row, col in np.ndindex(moduli.shape):
        for gauss_x in (-1 / np.sqrt(3), 1 / np.sqrt(3)):
            for gauss_y in (-1 / np.sqrt(3), 1 / np.sqrt(3)):
                xi = -1 + (2 * col + 1 + gauss_x) / nx
                eta = 1 - (2 * row + 1 + gauss_y) / ny
                dx = corners[:, 0] * (1 + corners[:, 1] * eta) / (2 * nx * dx_cell)
                dy = corners[:, 1] * (1 + corners[:, 0] * xi) / (2 * ny * dy_cell)
                b = np.zeros((3, 8))
                b[0, ::2], b[1, 1::2] = dx, dy
                b[2, ::2], b[2, 1::2] = dy, dx
                result += moduli[row, col] * (b.T @ constitutive @ b) * dx_cell * dy_cell / 4
    order = np.array([2, 3, 6, 7, 4, 5, 0, 1])
    global_matrix = np.zeros((8, 8))
    global_matrix[np.ix_(order, order)] = result
    return global_matrix


@pytest.mark.parametrize("lengths", [(4., 4.), (4.3, 3.8)])
def test_variable_material_integration_matches_independent_gauss_quadrature(lengths):
    scenario = get_run("Cantilever").updated(Lx=lengths[0], Ly=lengths[1], point_loads=[]).scenario
    multi, _ = engines((4, 4), 4, scenario)
    density = np.random.default_rng(6).uniform(0.2, 0.9, (4, 4))
    state = multi.solve(density)
    moduli = multi.material.stiffness(density, multi.problem.scenario.E0, multi.problem.scenario.Emin)
    expected = independent_subcell_matrix(moduli, multi.problem.scenario.nu,
                                         multi.problem.dx, multi.problem.dy)
    np.testing.assert_allclose(state.coarse_stiffness.toarray(), expected, atol=2e-16, rtol=2e-13)


def test_uniform_material_matches_the_standard_coarse_q4_mesh():
    multi, _ = engines((8, 12), 2)
    state = multi.solve(np.full((8, 12), 0.6))
    coarse_problem = make_problem(multi.problem.scenario, 0.5)
    reference = Q4PlaneStress()
    reference.initialize(coarse_problem, {})
    expected = reference.solve(np.full(coarse_problem.shape, 0.6))
    np.testing.assert_allclose(state.coarse_U, expected.U, rtol=2e-12, atol=2e-10)
    assert state.compliances == pytest.approx(expected.compliances, rel=2e-12)


def test_fine_point_and_hole_supports_are_enforced_without_snapping():
    scenario = get_run("Cantilever").updated(
        Lx=16, Ly=12, point_loads=[],
        point_constraints=[PointConstraint(x=5, y=5, dof="y")],
        holes=[HoleConfig(cx=6, cy=6, r_void=0.6, r_passive=1.5, kind="fixed")],
        load_cases=[LoadCase(Fmag=1, Fa=270, weight=0.4), LoadCase(Fmag=0.7, Fa=30, weight=0.6)],
    ).scenario
    multi, fine = engines((12, 16), 2, scenario)
    density = np.random.default_rng(8).uniform(0.3, 0.8, multi.problem.shape)
    density = np.clip(density, multi.problem.lower_bound, multi.problem.upper_bound)
    state, resolved = multi.solve(density), fine.solve(density)
    assert multi._conditions.shape[0] > 0
    np.testing.assert_allclose(state.U[multi.layout.fixed_dofs], 0, atol=2e-12)
    for case, (_, load) in enumerate(multi.layout.forces):
        assert load @ state.U[:, case] == pytest.approx(state.compliances[case], rel=2e-12)
        # The constrained coarse trial space is a subspace of fine Q4: it is
        # stiffer, not an independent high-fidelity resolution of fine features.
        assert state.compliances[case] <= resolved.compliances[case] * (1 + 1e-12)
    direction = np.random.default_rng(17).normal(size=density.shape)
    direction[multi.problem.upper_bound <= multi.problem.lower_bound] = 0
    direction /= np.linalg.norm(direction)
    gradient = -multi.stiffness_slope(state) * sum(
        weight * multi.strain_energy(state, case) for case, weight in enumerate(state.weights))
    step = 1e-4
    plus, minus = multi.solve(density + step * direction), multi.solve(density - step * direction)
    numerical = sum(w * (a - b) for w, a, b in zip(state.weights, plus.compliances, minus.compliances,
                                                 strict=True)) / (2 * step)
    assert np.sum(gradient * direction) == pytest.approx(numerical, rel=2e-6)


@pytest.mark.parametrize("filter_specs", [[], [{"type": "density", "rmin": 1.5}],
                                          [{"type": "pde_anisotropic", "rmin_x": 4, "rmin_y": 1}]])
def test_a_filter_smaller_than_one_analysis_cell_is_refused(filter_specs):
    run = get_run("MBB Beam").updated(method="q4_multiresolution+mma", m=0.4,
        method_params={"coarsening": 2}, filter_specs=filter_specs)
    with pytest.raises(ValueError, match="one analysis cell"):
        initialized_method(run)


def test_one_analysis_cell_of_filter_keeps_the_coarse_model_honest():
    # The artefact this rule prevents: below one analysis cell the coarse model claims a design
    # far stiffer than a fine Q4 analysis of the same density finds.
    from toporia.plugins.physics.q4_plane_stress import solve_fea
    run = get_run("MBB Beam").updated(method="q4_multiresolution+mma", m=1.0, max_iter=80, tol=0.0,
        method_params={"coarsening": 2}, filter_specs=[{"type": "density", "rmin": 2}])
    method = initialized_method(run)
    try:
        for iteration in range(1, 81):
            method.step(iteration)
        coarse = method.get_responses()["objective"]
        fine = float(solve_fea(method.problem, method.get_density(), 3.0)[2])
    finally:
        method.close()
    assert 0.9 < coarse / fine <= 1.0 + 1e-9


@pytest.mark.parametrize("filter_specs", [[{"type": "density", "rmin": 2}], [{"type": "density", "rmin": 3}]])
def test_fine_objective_and_volume_gradients_include_the_full_model_chain(filter_specs):
    run = get_run("MBB Beam").updated(method="q4_multiresolution+mma", m=0.4,
        method_params={"coarsening": 2}, filter_specs=filter_specs)
    method = initialized_method(run)
    model = method._model
    x = np.random.default_rng(13).uniform(0.35, 0.8, model.problem.shape)
    result = model.evaluate(x)
    # A larger step resolves the small cell sensitivities beside a large
    # total compliance without cancellation of sparse-solver roundoff.
    step = 1e-4
    for index in ((0, 2), (3, 8), (7, 21)):
        plus, minus = x.copy(), x.copy()
        plus[index] += step
        minus[index] -= step
        a, b = model.evaluate(plus), model.evaluate(minus)
        assert result.objective_gradient[index] == pytest.approx((a.objective - b.objective) / (2 * step), rel=1e-5)
        assert result.volume_gradient[index] == pytest.approx((a.volume - b.volume) / (2 * step), rel=1e-7)


@pytest.mark.parametrize("factor", [0, 1.5, 9, np.nan])
def test_invalid_factors_are_refused(factor):
    with pytest.raises(ValueError, match="integer"):
        engines(factor=factor)


def test_a_nondivisible_grid_is_refused_before_solving():
    with pytest.raises(ValueError, match="divisible"):
        engines((7, 12), 2)


def test_only_supported_elastic_energy_responses_are_offered():
    caps = Q4MultiresolutionModel.capabilities
    assert "compliance" in caps.objectives
    assert "stress" not in caps.constraints
    assert not caps.supports_springs and caps.dims == (2,)


def test_a_subcell_void_cut_exposes_artificial_stiffness_instead_of_certifying_connectivity():
    multi, fine = engines((8, 12), 2)
    density = np.ones((8, 12))
    density[:, 5] = 0  # one fine-cell cut inside a coarse element
    coarse_state, resolved = multi.solve(density), fine.solve(density)
    assert resolved.compliances[0] > 1e5 * coarse_state.compliances[0]
