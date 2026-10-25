"""test_heat.py — steady heat conduction: the engines, the response, the pyMOTO cross-check, the preset.

The decisive checks are two: a strip with a known temperature profile (the
engines reproduce the analytic maximum and thermal compliance), and pyMOTO's
own Poisson assembly (a different code gives the same thermal compliance and
gradient on the same design).
"""

import importlib.util
from dataclasses import replace

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario, Solver
from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.models.h8_heat import H8HeatModel
from toporia.plugins.models.q4_heat import Q4HeatModel
from toporia.plugins.physics.h8_heat import H8Heat
from toporia.plugins.physics.q4_heat import Q4Heat, element_conductivity
from toporia.plugins.problems import get_run
from toporia.plugins.responses.thermal_compliance import ThermalCompliance

SOURCE = 0.5


def _strip(Lz=0.0):
    """A strip L = 8 long, H = 2 wide, both short ends held at T = 0, unit conductivity, no point heat."""
    return Scenario(Lx=8.0, Ly=2.0, Lz=Lz,
                    edge_constraints=[EdgeConstraint("left"), EdgeConstraint("right")],
                    load_cases=[LoadCase(Fmag=0.0)], volfrac=1.0, Emin=1e-9)


def _engine(cls, scenario, m, **settings):
    problem = make_problem(scenario, m)
    engine = cls()
    engine.initialize(problem, {"heat_source": SOURCE, **settings})
    return problem, engine


# ── The element ───────────────────────────────────────────────────────────────

def test_the_square_element_is_the_classic_matrix():
    classic = np.array([[4, -1, -2, -1], [-1, 4, -1, -2], [-2, -1, 4, -1], [-1, -2, -1, 4]]) / 6.0
    assert element_conductivity() == pytest.approx(classic, abs=1e-14)
    assert element_conductivity(3.0, 3.0) == pytest.approx(classic, abs=1e-14)   # 2-D: scale does not matter


# ── An analytic profile ───────────────────────────────────────────────────────

@pytest.mark.parametrize("cls, Lz", [(Q4Heat, 0.0), (H8Heat, 2.0)])
def test_a_heated_strip_has_the_parabolic_profile(cls, Lz):
    """-k T'' = Q with T = 0 at both ends: T_max = Q L² / 8k in the middle, and C = Q² H (Lz) (L³ − h²L) / 12k.

    The compliance qᵀT sums the nodal temperatures with trapezoid weights, which is the integral of the
    parabola up to the h²L term (h = 1 the element length); the maximum is exact at the nodes.
    """
    scenario = _strip(Lz)
    problem, engine = _engine(cls, scenario, 1.0)
    state = engine.solve(np.ones(problem.shape))
    L, H = 8.0, 2.0
    assert state.T.max() == pytest.approx(SOURCE * L ** 2 / 8.0, rel=1e-10)
    cross_section = H * (Lz if Lz else 1.0)
    assert engine.thermal_compliance(state, 0) == pytest.approx(SOURCE ** 2 * cross_section * (L ** 3 - L) / 12.0, rel=1e-10)
    # The energy decomposition: thermal compliance = Σ k_e · T_eᵀ K_e T_e.
    assert np.sum(state.conductivity * state.energies[0].reshape(-1, order=engine.element_order)) \
        == pytest.approx(engine.thermal_compliance(state, 0), rel=1e-10)


def test_a_point_load_is_heat_input_and_supports_are_sinks():
    """No generation, Fmag watts entering at one corner of a bar held at T = 0 at the other end."""
    def solved(fmag):
        scenario = replace(_strip(), edge_constraints=[EdgeConstraint("left")], point_loads=[PointLoad(8.0, 0.0)],
                           load_cases=[LoadCase(Fmag=fmag)])
        problem, engine = _engine(Q4Heat, scenario, 1.0, heat_source=0.0)
        return engine, engine.solve(np.ones(problem.shape))

    engine, state = solved(3.0)
    assert state.T[engine.fixed, 0].max() == 0.0                    # the sink stays at zero
    assert state.T.min() >= -1e-12 and state.T.max() > 0.0          # heat only warms the plate
    # The load node is the hottest, and C = qᵀT = Fmag · T there; doubling the heat quadruples C.
    assert engine.thermal_compliance(state, 0) == pytest.approx(3.0 * state.T.max(), rel=1e-12)
    other, doubled = solved(6.0)
    assert other.thermal_compliance(doubled, 0) == pytest.approx(4.0 * engine.thermal_compliance(state, 0), rel=1e-12)


# ── Gradients ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("plugin", ["model:q4_heat", "model:h8_heat", "model:pymoto_heat", "response:thermal_compliance"])
def test_the_heat_parts_conform(plugin):
    if plugin.endswith("pymoto_heat"):
        pytest.importorskip("pymoto")
    conformance(plugin).assert_ok()


@pytest.mark.parametrize("cls, Lz", [(Q4Heat, 0.0), (H8Heat, 3.0)])
def test_thermal_compliance_gradient_matches_finite_differences(cls, Lz):
    scenario = replace(get_run("Heat Sink").scenario, Lz=Lz)
    problem, engine = _engine(cls, scenario, 0.12 if Lz else 0.2)
    response = ThermalCompliance()
    response.setup(engine, problem, {})
    rng = np.random.default_rng(3)
    density = np.clip(rng.uniform(0.2, 0.9, problem.shape), problem.lower_bound, problem.upper_bound)
    result = response.evaluate(engine.solve(density))
    for index in np.argsort(-np.abs(result.gradient.ravel()))[:5]:
        up, down = density.copy(), density.copy()
        up.reshape(-1)[index] += 1e-6
        down.reshape(-1)[index] -= 1e-6
        fd = (response.evaluate(engine.solve(up), False).value - response.evaluate(engine.solve(down), False).value) / 2e-6
        assert result.gradient.reshape(-1)[index] == pytest.approx(fd, rel=1e-5)
    assert np.all(result.gradient <= 0)      # more conductor never raises the temperature


def test_the_response_is_offered_only_where_the_physics_provides_it():
    assert "thermal_compliance" in Q4HeatModel.capabilities.objectives
    assert "thermal_compliance" in H8HeatModel.capabilities.objectives
    assert "compliance" not in Q4HeatModel.capabilities.objectives
    from toporia.plugins.models.q4 import Q4Model
    assert "thermal_compliance" not in Q4Model.capabilities.objectives


# ── pyMOTO ────────────────────────────────────────────────────────────────────

def _model(cls, run, settings=None):
    problem = make_problem(run.scenario, run.solver.m)
    model = cls()
    model.initialize(problem, run.solver, resolve_params(cls.name, cls.params, settings or {}))
    return problem, model


@pytest.mark.skipif(importlib.util.find_spec("pymoto") is None, reason="optional dependency: pip install pymoto")
def test_pymoto_gives_the_same_thermal_compliance():
    """A different code (pyMOTO's AssemblePoisson, its own load vector and sensitivities) on one design."""
    from toporia.plugins.models.pymoto_heat import PymotoHeatModel
    base = get_run("Heat Sink")
    scenario = replace(base.scenario, point_loads=[PointLoad(90.0, 90.0)],
                       load_cases=[LoadCase(Fmag=0.7, weight=0.6), LoadCase(Fmag=0.2, weight=0.4)])
    # A filter radius of one element leaves the design as it is; Toporia's pipeline has no filter.
    foreign_run = replace(base, scenario=scenario)
    native_run = replace(foreign_run, solver=replace(foreign_run.solver, filter_specs=[]))
    problem, native = _model(Q4HeatModel, native_run)
    _, foreign = _model(PymotoHeatModel, foreign_run, {"rmin": 1.0})

    rng = np.random.default_rng(5)
    x = np.clip(rng.uniform(0.1, 1.0, problem.shape), problem.lower_bound, problem.upper_bound)
    assert foreign.physical(x.ravel()) == pytest.approx(x, abs=1e-12)

    a, b = native.evaluate(x), foreign.evaluate(x.ravel())
    print(f"thermal compliance: q4_heat {a.objective:.10g}  pymoto_heat {b.objective:.10g}")
    assert b.objective == pytest.approx(a.objective, rel=1e-9)
    # Elements of the solid sink ring are pinned: pyMOTO zeroes their sensitivity, Toporia leaves it to the updater.
    movable = problem.upper_bound > problem.lower_bound
    assert b.objective_gradient.reshape(problem.shape)[movable] == pytest.approx(a.objective_gradient[movable], rel=1e-8)
    assert b.volume == pytest.approx(a.volume, rel=1e-12)


# ── The preset ────────────────────────────────────────────────────────────────

def test_the_heat_sink_preset_runs_and_cools_the_plate():
    run = get_run("Heat Sink").updated(max_iter=15, tol=0.0, save_every=0)
    assert run.solver.method == "q4_heat+oc"
    method = initialized_method(run)
    first = None
    for iteration in range(1, 16):
        method.step(iteration)
        first = first or method.get_responses()["objective"]
    last = method.get_responses()["objective"]
    print(f"heat sink: thermal compliance {first:.6g} -> {last:.6g} after 15 iterations")
    assert np.isfinite(last) and last < 0.7 * first
    density = method.get_density()
    assert density.shape == (50, 50) and abs(density.mean() - 0.4) < 0.02


def test_the_heat_sink_scenario_is_not_a_structural_one():
    assert get_run("Heat Sink").scenario.objective == {"type": "thermal_compliance"}
    assert Solver(method="q4_heat+oc").method == "q4_heat+oc"
