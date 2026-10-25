"""test_dynamics.py — vibration: eigenfrequencies and harmonic response.

What is pinned:
  * the cantilever's first bending frequency against Euler-Bernoulli beam theory;
  * the eigenvalue and harmonic sensitivities against finite differences;
  * Pedersen's mass fix against spurious modes in void;
  * the lowest eigenvalues against pyMOTO's own mass assembly and eigensolver;
  * the preset, run for a few iterations.
"""

import importlib.util

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario
from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.physics.q4_dynamic import Q4Dynamic, mass_interpolation
from toporia.plugins.problems import get_run
from toporia.plugins.responses.eigenfrequency import soft_minimum


def _engine(scenario, m, **settings):
    problem = make_problem(scenario, m)
    engine = Q4Dynamic()
    engine.initialize(problem, resolve_params("q4_dynamic", Q4Dynamic.params, settings))
    return problem, engine


def _cantilever(length=20.0, depth=1.0):
    return Scenario(Lx=length, Ly=depth, nu=0.0,
                    edge_constraints=[EdgeConstraint("left", "both")],
                    point_loads=[PointLoad(length, depth / 2)],
                    load_cases=[LoadCase(Fmag=1.0, Fa=270.0)])


def _random_density(problem, seed=3):
    return np.random.default_rng(seed).uniform(0.2, 0.95, problem.shape)


def test_cantilever_first_bending_frequency_matches_euler_bernoulli():
    length, depth, m = 20.0, 1.0, 4
    problem, engine = _engine(_cantilever(length, depth), m, low_density_below=0.0)
    omega = np.sqrt(engine.eigenvalues(engine.solve(np.ones(problem.shape)), 2))
    # w1 = (1.8751)^2 sqrt(E I / (rho A L^4)), unit E and rho, plane stress with nu = 0
    reference = 1.8751 ** 2 * np.sqrt((depth ** 3 / 12) / (depth * length ** 4))
    assert omega[0] == pytest.approx(reference, rel=0.03), (omega[0], reference)
    # the second mode is the second bending mode, (4.6941)^2 sqrt(...)
    assert omega[1] == pytest.approx(reference * (4.6941 / 1.8751) ** 2, rel=0.06)


def test_lumped_mass_gives_lower_frequencies_than_consistent():
    problem, consistent = _engine(_cantilever(), 2, low_density_below=0.0)
    _, lumped = _engine(_cantilever(), 2, low_density_below=0.0, mass_type="lumped")
    ones = np.ones(problem.shape)
    assert lumped.eigenvalues(lumped.solve(ones), 1)[0] < consistent.eigenvalues(consistent.solve(ones), 1)[0]


def test_attached_mass_lowers_the_frequency_as_expected():
    scenario = _cantilever()
    problem, bare = _engine(scenario, 2, low_density_below=0.0)
    _, loaded = _engine(scenario, 2, low_density_below=0.0, attached_mass=5.0)
    ones = np.ones(problem.shape)
    lam_bare = bare.eigenvalues(bare.solve(ones), 1)[0]
    lam_loaded = loaded.eigenvalues(loaded.solve(ones), 1)[0]
    # a tip mass of 5 on a beam of mass 20: lambda falls by about (0.24 * 20) / (0.24 * 20 + 5)
    assert 0.3 < lam_loaded / lam_bare < 0.7


@pytest.mark.parametrize("settings", [{"low_density_below": 0.0}, {"low_density_below": 0.1},
                                      {"mass_type": "lumped", "attached_mass": 1.0}])
def test_eigenvalue_sensitivity_matches_finite_differences(settings):
    scenario = Scenario(Lx=8.0, Ly=2.0, edge_constraints=[EdgeConstraint("left", "both")],
                        point_loads=[PointLoad(8.0, 1.0)])
    problem, engine = _engine(scenario, 1.5, **settings)
    density = _random_density(problem)
    density[0, :3] = 0.05                       # some low-density elements, to cover Pedersen's branch
    state = engine.solve(density)
    n = 3
    for mode in range(n):
        gradient = engine.eigenvalue_sensitivity(state, mode)
        for index in [(0, 1), (2, 5), (problem.nely - 1, problem.nelx - 1), (1, 2)]:
            step = 1e-6
            up, down = density.copy(), density.copy()
            up[index] += step
            down[index] -= step
            numeric = (engine.eigenvalues(engine.solve(up), n)[mode]
                       - engine.eigenvalues(engine.solve(down), n)[mode]) / (2 * step)
            assert gradient[index] == pytest.approx(numeric, rel=1e-4, abs=1e-9), (mode, index)


def test_harmonic_sensitivity_matches_finite_differences():
    scenario = Scenario(Lx=8.0, Ly=2.0, edge_constraints=[EdgeConstraint("left", "both")],
                        point_loads=[PointLoad(8.0, 1.0)])
    problem, engine = _engine(scenario, 1.5, attached_mass=1.0)
    density = _random_density(problem, seed=5)
    state = engine.solve(density)
    omega = 0.6 * np.sqrt(engine.eigenvalues(state, 1)[0])          # below the first resonance
    gradient = engine.dynamic_compliance_sensitivity(state, 0, omega)
    for index in [(0, 0), (1, 4), (problem.nely - 1, 3), (2, problem.nelx - 1)]:
        step = 1e-6
        up, down = density.copy(), density.copy()
        up[index] += step
        down[index] -= step
        numeric = (engine.dynamic_compliance(engine.solve(up), 0, omega)
                   - engine.dynamic_compliance(engine.solve(down), 0, omega)) / (2 * step)
        assert gradient[index] == pytest.approx(numeric, rel=1e-4, abs=1e-9), index


def test_harmonic_response_at_zero_frequency_is_the_static_compliance():
    problem, engine = _engine(_cantilever(), 2)
    state = engine.solve(np.full(problem.shape, 0.7))
    assert engine.dynamic_compliance(state, 0, 0.0) == pytest.approx(engine.compliance(state, 0), rel=1e-9)


def test_harmonic_compliance_grows_towards_the_first_resonance():
    problem, engine = _engine(_cantilever(), 2)
    state = engine.solve(np.ones(problem.shape))
    w1 = np.sqrt(engine.eigenvalues(state, 1)[0])
    low, high = (engine.dynamic_compliance(state, 0, f * w1) for f in (0.2, 0.9))
    assert high > 3 * low > 0


def test_the_mass_fix_removes_spurious_modes_in_void():
    """A beam whose lower half is near-void: without the fix the void's own 'modes' set the lowest eigenvalue."""
    scenario = _cantilever(length=10.0, depth=2.0)
    problem, fixed = _engine(scenario, 2)
    _, plain = _engine(scenario, 2, low_density_below=0.0)
    density = np.full(problem.shape, 1e-3)
    density[:problem.nely // 2, :] = 1.0        # the solid half; the rest is void
    lam_fixed = fixed.eigenvalues(fixed.solve(density), 1)[0]
    lam_plain = plain.eigenvalues(plain.solve(density), 1)[0]
    assert lam_plain < 0.1 * lam_fixed, (lam_plain, lam_fixed)


def test_mass_interpolation_is_continuous_and_linear_above_the_threshold():
    rho = np.array([0.0, 0.05, 0.1 - 1e-12, 0.1, 0.5, 1.0])
    mass, slope = mass_interpolation(rho, 0.1, 6.0)
    assert mass[2] == pytest.approx(mass[3], abs=1e-9)
    assert mass[4:] == pytest.approx([0.5, 1.0]) and slope[3:] == pytest.approx(1.0)
    assert mass[1] == pytest.approx(0.1 * 0.5 ** 6)


def test_soft_minimum_is_never_above_the_lowest_and_tends_to_it():
    values = np.array([1.0, 1.3, 2.0])
    low, _ = soft_minimum(values, 4.0)
    high, _ = soft_minimum(values, 80.0)
    assert low < high <= 1.0 and high == pytest.approx(1.0, rel=0.01)
    assert soft_minimum(values[:1], 16.0)[0] == pytest.approx(1.0)


def test_eigenfrequency_objective_gradient_through_the_model():
    """The model's objective gradient with three modes aggregated, through the density filter."""
    from toporia.plugins.models.q4_dynamic import Q4DynamicModel
    run = get_run("Vibrating Beam").updated(m=2.0)
    problem = make_problem(run.scenario, run.solver.m)
    model = Q4DynamicModel()
    model.initialize(problem, run.solver, resolve_params("q4_dynamic", Q4DynamicModel.params, {"attached_mass": 2.0}))
    x = np.random.default_rng(1).uniform(0.3, 0.9, model.initial_design().shape)
    result = model.evaluate(x)
    for index in [(0, 3), (1, 5), (0, 12), (1, 15)]:
        step = 1e-6
        up, down = x.copy(), x.copy()
        up[index] += step
        down[index] -= step
        numeric = (model.evaluate(up, gradients=False).objective
                   - model.evaluate(down, gradients=False).objective) / (2 * step)
        assert result.objective_gradient[index] == pytest.approx(numeric, rel=1e-4, abs=1e-9), index


def test_the_preset_raises_the_fundamental_frequency():
    run = get_run("Vibrating Beam").updated(m=3.0, max_iter=15, tol=0.0)
    method = initialized_method(run)
    method.step(1)
    first = method.get_responses()
    for iteration in range(2, 16):
        method.step(iteration)
    last = method.get_responses()
    assert np.isfinite(method.get_density()).all()
    assert last["objective"] < first["objective"] - 0.2      # the (negated, scaled) frequency went up


@pytest.mark.skipif(importlib.util.find_spec("pymoto") is None, reason="optional dependency: pip install pymoto")
def test_lowest_eigenvalues_agree_with_pymoto():
    from toporia.plugins.models.pymoto_dynamic import PymotoDynamicModel
    run = get_run("Vibrating Beam").updated(m=4.0, method="pymoto_dynamic", method_params={"attached_mass": 2.0})
    problem = make_problem(run.scenario, run.solver.m)
    values = {"rmin": 1.5, "penal": 3.0, "mass_density": 1.0, "low_density_below": 0.1,
              "low_density_exponent": 6.0, "attached_mass": 2.0}
    foreign = PymotoDynamicModel()
    foreign.initialize(problem, run.solver, values)
    x = np.random.default_rng(2).uniform(0.3, 0.95, foreign.initial_design().shape)
    result = foreign.evaluate(x)

    engine = Q4Dynamic()
    engine.initialize(problem, resolve_params("q4_dynamic", Q4Dynamic.params, {"attached_mass": 2.0}))
    native = engine.eigenvalues(engine.solve(foreign.physical(x)), 3)
    lowest = np.asarray(foreign.s_eigenvalues.state)
    assert lowest == pytest.approx(native, rel=1e-5)
    assert result.reported["omega_1"] == pytest.approx(np.sqrt(native[0]), rel=1e-5)

    # the pyMOTO network's own gradient is consistent with its objective
    for index in [5, 33, 61]:
        step = 1e-6
        up, down = x.copy(), x.copy()
        up[index] += step
        down[index] -= step
        numeric = (foreign.evaluate(up, gradients=False).objective
                   - foreign.evaluate(down, gradients=False).objective) / (2 * step)
        assert result.objective_gradient[index] == pytest.approx(numeric, rel=1e-3, abs=1e-8), index
