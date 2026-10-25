"""Spring energy, signed adjoints, physical scaling and force inversion."""

from dataclasses import replace

import numpy as np
import pytest

from toporia.checks.common import iterate
from toporia.engine.loop import initialized_method
from toporia.framework import LoadCase, PointSpring, read_param
from toporia.framework.problem.files import fingerprint, from_dict, to_dict
from toporia.framework.problem.mesh import make_problem
from toporia.framework.problem.scenario import Scenario
from toporia.plugins.models.assembled import material_law
from toporia.plugins.physics.q4_mechanism import Q4Mechanism
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
from toporia.plugins.problems import get_run
from toporia.plugins.responses.compliance import Compliance
from toporia.plugins.responses.output_displacement import OutputDisplacement


def _engine(run=None):
    run = get_run("Force Inverter").updated(m=0.2) if run is None else run
    problem = make_problem(run.scenario, run.solver.m)
    engine = Q4Mechanism()
    engine.initialize(problem, {}, material_law(run.solver))
    return run, problem, engine


def _response(engine, problem, spec=None):
    spec = problem.scenario.objective if spec is None else spec
    response = OutputDisplacement()
    response.setup(engine, problem, {key: spec[key] for key in ("x", "y", "angle")})
    return response


def test_springs_round_trip_and_are_addressable_in_scenario_paths():
    run = get_run("Force Inverter")
    assert from_dict(Scenario, to_dict(run.scenario)) == run.scenario
    changed = run.updated(**{"point_springs[1].stiffness": 0.02})
    assert changed.scenario.point_springs[1].stiffness == 0.02
    assert read_param(changed, "point_springs[1].stiffness") == 0.02
    assert run.scenario.point_springs[1].stiffness == 0.01
    integer_input = Scenario(point_springs=[PointSpring(0, 20, 1)])
    assert fingerprint(from_dict(Scenario, to_dict(integer_input))) == fingerprint(integer_input)


def test_unaware_models_reject_springs_even_with_a_supported_objective():
    run = get_run("Force Inverter").updated(objective={"type": "compliance"})
    for method in ("q4+mma", "pymoto_elastic+mma", "levelset"):
        with pytest.raises(ValueError, match="point springs"):
            initialized_method(run.updated(method=method))


def test_without_springs_the_new_engine_agrees_with_unchanged_q4():
    run = get_run("MBB Beam").updated(m=0.3)
    _, problem, engine = _engine(run)
    native = Q4PlaneStress()
    native.initialize(problem, {}, material_law(run.solver))
    rho = np.random.default_rng(3).uniform(0.4, 0.8, problem.shape)
    expected, actual = native.solve(rho), engine.solve(rho)
    np.testing.assert_allclose(actual.U, expected.U, rtol=2e-10, atol=1e-10)
    np.testing.assert_allclose(actual.compliances, expected.compliances, rtol=2e-10)


def test_external_work_equals_material_plus_spring_energy():
    _, problem, engine = _engine()
    rho = np.full(problem.shape, 0.6)
    state = engine.solve(rho)
    for case, (_, force) in enumerate(engine.layout.forces):
        material = np.sum(state.stiffness * state.energies[case].reshape(-1, order="F"))
        spring = np.sum(engine.spring_diagonal * state.U[:, case] ** 2)
        assert force @ state.U[:, case] == pytest.approx(material + spring, rel=1e-11)
        assert engine.compliance(state, case) == pytest.approx(material + spring, rel=1e-11)
        assert spring > 0


@pytest.mark.parametrize("kind", ["output", "compliance"])
def test_spring_state_and_its_adjoint_have_exact_density_gradients(kind):
    run = get_run("Force Inverter").updated(m=0.2,
        load_cases=[LoadCase(0.001, 0, 0.7), LoadCase(0.002, 60, 0.3)])
    _, problem, engine = _engine(run)
    response = _response(engine, problem) if kind == "output" else Compliance()
    if kind == "compliance":
        response.setup(engine, problem, {})
    rho = np.random.default_rng(4).uniform(0.3, 0.8, problem.shape)
    result = response.evaluate(engine.solve(rho))
    assert response.evaluate(engine.solve(rho), gradient=False).value == result.value
    for index in np.argsort(-np.abs(result.gradient.ravel()))[:8]:
        direction = np.zeros_like(rho)
        direction.flat[index] = 1e-5
        fd = (response.evaluate(engine.solve(rho + direction), gradient=False).value
              - response.evaluate(engine.solve(rho - direction), gradient=False).value) / 2e-5
        assert fd == pytest.approx(result.gradient.flat[index], rel=5e-5, abs=2e-11)


def test_probe_direction_and_force_scaling_are_signed_and_linear():
    run, problem, engine = _engine()
    rho = np.full(problem.shape, 0.5)
    state = engine.solve(rho)
    response = _response(engine, problem)
    value = response.evaluate(state)
    reverse = _response(engine, problem, {"x": 40, "y": 20, "angle": 0})
    assert reverse.evaluate(state).value == pytest.approx(-value.value)
    np.testing.assert_allclose(reverse.evaluate(state).gradient, -value.gradient, atol=1e-14)
    doubled = run.updated(load_cases=[LoadCase(0.002, 0)])
    _, problem2, engine2 = _engine(doubled)
    actual = _response(engine2, problem2).evaluate(engine2.solve(rho))
    assert actual.value == pytest.approx(2 * value.value)
    np.testing.assert_allclose(actual.gradient, 2 * value.gradient, rtol=1e-12, atol=1e-14)


def test_coincident_springs_add_and_outside_ports_are_rejected():
    run = get_run("Force Inverter").updated(m=0.2)
    _, _, expected = _engine(run)
    split = replace(run.scenario, point_springs=[PointSpring(0, 20, 0.004),
                    PointSpring(0, 20, 0.006), PointSpring(40, 20, 0.01)])
    _, _, actual = _engine(replace(run, scenario=split))
    np.testing.assert_allclose(actual.spring_diagonal, expected.spring_diagonal)
    for spring in (PointSpring(-1, 20, 0.1), PointSpring(41, 20, 0.1)):
        with pytest.raises(ValueError, match="inside the design domain"):
            _engine(run.updated(point_springs=[spring]))


def test_springs_alone_do_not_add_an_unrequested_clamp_and_balance_the_load():
    run = get_run("Force Inverter").updated(m=0.2, point_constraints=[],
        point_springs=[PointSpring(0, 0, 0.01, "x"), PointSpring(0, 0, 0.01, "y"),
                       PointSpring(0, 40, 0.01, "x")])
    _, problem, engine = _engine(run)
    assert not np.any(problem.fixed_nodes)
    assert engine.layout.fixed_dofs.size == 0
    state = engine.solve(np.full(problem.shape, 0.6))
    reactions = engine.spring_diagonal * state.U[:, 0]
    force = engine.layout.forces[0][1]
    assert reactions[::2].sum() == pytest.approx(force[::2].sum(), abs=1e-12)
    assert reactions[1::2].sum() == pytest.approx(force[1::2].sum(), abs=1e-12)


def test_insufficient_spring_restraint_is_rejected_before_solving():
    run = get_run("Force Inverter").updated(m=0.2, point_constraints=[],
                                            point_springs=[PointSpring(0, 20, 0.01)])
    with pytest.raises(ValueError, match="rigid-body motion"):
        _engine(run)


@pytest.mark.parametrize("values", [(0, 0, -1, "x"), (0, 0, 1, "z"), (np.nan, 0, 1, "x")])
def test_invalid_spring_definitions_are_rejected(values):
    with pytest.raises(ValueError):
        PointSpring(*values)


def test_the_preset_produces_feasible_force_inversion_within_the_passivity_bound():
    run = get_run("Force Inverter").updated(m=0.4, save_every=0)
    method = initialized_method(run)
    iterate(method, 200, tol=0.001)
    result = method._model.evaluate(method.x, gradients=False)
    displacement = result.reported["output_displacement"]
    assert result.objective == -displacement
    assert displacement > 0.001  # output is now opposite to the input force
    assert method.get_density().mean() <= 0.4001
    # F*u_in >= k_in*u_in^2 + k_out*u_out^2 gives this passive upper bound.
    bound = 0.001 / (2 * np.sqrt(0.01 * 0.01))
    assert displacement <= bound
