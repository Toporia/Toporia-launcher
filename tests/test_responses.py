"""test_responses.py — objectives, constraints, and the capability check.

A scenario now says what to minimise and what to limit.  These tests pin the
declarations, the parameter paths into them, the check that refuses a method
which cannot deliver, and — with pyMOTO — that a stress constraint actually
holds, not merely that something moved.
"""

import importlib.util
from dataclasses import replace

import numpy as np
import pytest

from toporia.core import CONSTRAINT_ROLE, OBJECTIVE_ROLE, apply_param, read_param
from toporia.core.problem import RectangularProblem
from toporia.core.serialize import load, save
from toporia.engine.runner import initialized_method
from toporia.library.catalog import parameter_paths
from toporia.library.methods import METHODS
from toporia.library.problems import get_run
from toporia.library.responses import RESPONSES, check_responses, responses_for

requires_pymoto = pytest.mark.skipif(importlib.util.find_spec("pymoto") is None,
                                     reason="optional dependency: pip install pymoto")
STRESS = {"type": "stress", "limit": 10.0}


# ── Declarations ──────────────────────────────────────────────────────────────

def test_responses_are_discovered_with_their_roles():
    assert RESPONSES.names() == ["compliance", "volume", "stress"]
    assert [c.name for c in responses_for(OBJECTIVE_ROLE)] == ["compliance", "volume"]
    assert [c.name for c in responses_for(CONSTRAINT_ROLE)] == ["stress"]


def test_the_default_scenario_minimises_compliance_under_the_volume_budget_only():
    scenario = get_run("MBB Beam").scenario
    assert scenario.objective == {"type": "compliance"}
    assert scenario.constraints == []


def test_scenarios_with_objectives_and_constraints_round_trip_through_json(tmp_path):
    scenario = replace(get_run("MBB Beam").scenario, objective={"type": "volume"}, constraints=[dict(STRESS)])
    assert load(save(scenario, tmp_path / "s.scenario.json")) == scenario


# ── Parameter paths ───────────────────────────────────────────────────────────

def test_constraint_parameters_are_addressable_by_path():
    base = get_run("MBB Beam").updated(constraints=[dict(STRESS)])
    run = apply_param(base, "constraints[0].limit", 5.0)
    assert read_param(run, "constraints[0].limit") == 5.0
    assert base.scenario.constraints[0]["limit"] == 10.0   # the input is never mutated


def test_constraint_paths_are_offered_only_to_methods_that_can_enforce_them():
    pymoto = [p for _, p in parameter_paths("pymoto", [], 1, {"type": "compliance"}, [STRESS])]
    oc = [p for _, p in parameter_paths("density", [], 1, {"type": "compliance"}, [STRESS])]
    assert {"constraints[0].limit", "constraints[0].p", "constraints[0].q"} <= set(pymoto)
    assert "constraints[0].adaptive" not in pymoto        # booleans cannot be swept
    assert not any(p.startswith("constraints[") for p in oc)


# ── The capability check ──────────────────────────────────────────────────────

def test_capabilities_say_what_each_method_can_do():
    density = METHODS.get("density").capabilities
    assert (density.objectives, density.constraints, density.max_constraints) == (("compliance",), (), 0)
    pymoto = METHODS.get("pymoto").capabilities
    assert set(pymoto.objectives) == {"compliance", "volume"}
    assert pymoto.constraints == ("stress",) and pymoto.max_constraints is None
    # pyMOTO's GCMMA could take constraints, but the Q4 model cannot compute stress.
    assert METHODS.get("density_gcmma").capabilities.constraints == ()


@pytest.mark.parametrize("method", ["density", "density_mma", "levelset", "density_gcmma"])
def test_a_method_refuses_a_constraint_it_cannot_enforce_and_names_one_that_can(method):
    run = get_run("MBB Beam").updated(method=method, constraints=[dict(STRESS)], m=0.3)
    with pytest.raises(ValueError, match=r"cannot enforce \['stress'\].*Methods that can: \['pymoto'\]"):
        initialized_method(run)


def test_optimality_criteria_refuses_to_minimise_volume():
    run = get_run("MBB Beam").updated(objective={"type": "volume"}, constraints=[dict(STRESS)], m=0.3)
    with pytest.raises(ValueError, match="cannot minimise 'volume'"):
        initialized_method(run)


def test_minimising_volume_without_a_constraint_is_refused():
    scenario = replace(get_run("MBB Beam").scenario, objective={"type": "volume"})
    with pytest.raises(ValueError, match="needs at least one constraint"):
        check_responses(scenario)


def test_a_misspelt_response_parameter_fails_before_any_computation():
    run = get_run("MBB Beam").updated(method="pymoto", constraints=[{"type": "stress", "limt": 5.0}])
    with pytest.raises(ValueError, match="limt"):
        initialized_method(run)


def test_a_response_cannot_play_a_role_it_does_not_declare():
    scenario = replace(get_run("MBB Beam").scenario, objective={"type": "stress"})
    with pytest.raises(ValueError, match="cannot be used as the objective"):
        check_responses(scenario)


# ── Stress constraints through pyMOTO ─────────────────────────────────────────

def _optimise(run):
    method = initialized_method(run)
    for iteration in range(1, run.solver.max_iter + 1):
        method.step(iteration)
    return method


def _peak_stress(run, design=None):
    """True (un-aggregated) peak relaxed stress of a design, or of the starting design."""
    from toporia.library.models.pymoto_elastic import PymotoElasticModel
    measuring = run.updated(constraints=[{"type": "stress", "limit": 1e9}])
    model = PymotoElasticModel()
    model.initialize(RectangularProblem(measuring.scenario, measuring.solver.m), measuring.solver,
                     {"penal": 3.0, "rmin": 1.5})
    return model.evaluate(model.initial_design() if design is None else design).reported["max_stress"]


@requires_pymoto
@pytest.mark.parametrize("problem", ["MBB Beam", "Drone Arm"])   # one and two load cases
def test_the_stress_gradient_matches_finite_differences(problem):
    from toporia.library.models.pymoto_elastic import PymotoElasticModel
    # Fixed scaling: the adaptive factor is recomputed at every evaluation but
    # held constant in the gradient (by design), so finite differences of the
    # adaptive constraint cannot match its gradient.  This checks the p-norm itself.
    run = get_run(problem).updated(method="pymoto", m=0.3, volfrac=0.4,
                                   constraints=[{**STRESS, "adaptive": False}])
    model = PymotoElasticModel()
    model.initialize(RectangularProblem(run.scenario, run.solver.m), run.solver, {"penal": 3.0, "rmin": 1.5})
    rng = np.random.default_rng(1)
    lower, upper = model.bounds()
    x = np.clip(model.initial_design() + rng.uniform(-0.2, 0.2, lower.size), lower, upper)

    gradient = model.evaluate(x).constraints[0].gradient
    free = np.flatnonzero(upper > lower)
    for i in rng.choice(free, 6, replace=False):
        h = 1e-5
        plus, minus = x.copy(), x.copy()
        plus[i] += h
        minus[i] -= h
        fd = (model.evaluate(plus).constraints[0].value - model.evaluate(minus).constraints[0].value) / (2 * h)
        assert gradient[i] == pytest.approx(fd, rel=1e-2, abs=1e-8), f"element {i}"


@requires_pymoto
def test_a_stress_constraint_holds_its_limit_within_the_volume_budget():
    """Both limits, not just the stress: an optimiser can meet one by breaking the other.

    0.9 x the stiffest design's peak is achievable with 50 % material, so a
    correct run must end with the peak at or under the limit AND within budget.
    """
    base = get_run("MBB Beam").updated(method="pymoto", m=0.4, max_iter=80, tol=0.0)
    peak_free = _peak_stress(base, _optimise(base).x)
    limit = 0.9 * peak_free

    responses = _optimise(base.updated(constraints=[{"type": "stress", "limit": limit}])).get_responses()
    assert responses["max_stress"] <= 1.01 * limit, (responses["max_stress"], limit)
    assert responses["volume"] <= 1.01 * base.scenario.volfrac, responses["volume"]
    assert responses["max_stress"] < 0.95 * peak_free      # a genuinely different design


@requires_pymoto
def test_minimising_volume_under_a_stress_limit_saves_material_and_holds_the_limit():
    """The recipe the Volume response advises: start full, small move limit."""
    full = get_run("MBB Beam").updated(method="pymoto", m=0.4, max_iter=60, tol=0.0, volfrac=1.0)
    limit = 2.0 * _peak_stress(full)
    run = full.updated(objective={"type": "volume"}, constraints=[{"type": "stress", "limit": limit}],
                       **{"method.move": 0.05})
    responses = _optimise(run).get_responses()

    assert responses["volume"] < 0.6                       # well below the full start
    assert responses["max_stress"] <= 1.01 * limit         # the true peak honours the limit
    assert "compliance" in responses                       # still recorded when not the objective


# ── Reporting broken limits ───────────────────────────────────────────────────

def test_a_run_that_meets_its_limits_is_recorded_as_feasible(tmp_path):
    import json

    from toporia.engine.runner import run_single
    run = get_run("MBB Beam").updated(m=0.3, max_iter=10, tol=0.0, save_every=0).with_output_dir(tmp_path)
    run_single(run)
    result = json.loads((tmp_path / "run.json").read_text())["result"]
    assert result["feasible"] is True
    assert [entry["name"] for entry in result["limits"]] == ["volume budget"]


@requires_pymoto
def test_an_impossible_stress_limit_is_reported_not_hidden(tmp_path, capsys):
    """0.6 x the stiffest design's peak needs more than 50 % material.

    The optimiser meets the stress limit by using more material; the run must
    say so in the log and in run.json instead of presenting it as a success.
    """
    import json

    from toporia.engine.runner import run_single
    base = get_run("MBB Beam").updated(method="pymoto", m=0.4, max_iter=60, tol=0.0, save_every=0)
    limit = 0.6 * _peak_stress(base, _optimise(base).x)
    run = base.updated(constraints=[{"type": "stress", "limit": limit}]).with_output_dir(tmp_path)
    run_single(run)

    result = json.loads((tmp_path / "run.json").read_text())["result"]
    assert result["feasible"] is False
    broken = [entry["name"] for entry in result["limits"] if entry["satisfied"] is False]
    assert broken                                          # at least one limit is reported broken
    assert "WARNING" in capsys.readouterr().out


def test_limits_are_judged_on_the_exact_value_when_one_is_reported():
    from toporia.engine.feasibility import check_limits
    scenario = replace(get_run("MBB Beam").scenario, constraints=[{"type": "stress", "limit": 4.0}])
    # The p-norm says 10 % over; the true peak is 2 % under: the limit is met.
    report = check_limits(scenario, {"volume": 0.5, "constraint_0_stress": 0.10,
                                     "constraint_0_stress_exact": -0.02})
    assert all(entry["satisfied"] for entry in report)
    assert report[1]["value"] == pytest.approx(3.92)       # shown in the user's units

    over_budget = check_limits(scenario, {"volume": 0.56, "constraint_0_stress": -0.1})
    assert over_budget[0]["satisfied"] is False


def test_minimising_volume_prints_its_advice(capsys):
    """The failure mode is silent (the design just empties), so the guidance is printed up front."""
    run = get_run("MBB Beam").updated(method="pymoto", objective={"type": "volume"},
                                      constraints=[dict(STRESS)], m=0.3)
    try:
        initialized_method(run)
    except ImportError:
        pass   # without pyMOTO the method cannot be built, but the advice comes first
    assert "set the volume fraction to 1.0" in capsys.readouterr().out


@requires_pymoto
def test_several_constraints_are_enforced_and_reported_separately():
    run = get_run("MBB Beam").updated(method="pymoto", m=0.3, max_iter=3, tol=0.0,
                                      constraints=[{"type": "stress", "limit": 50.0, "p": 6.0},
                                                   {"type": "stress", "limit": 60.0, "p": 12.0}])
    responses = _optimise(run).get_responses()
    assert {"constraint_0_stress", "constraint_1_stress", "max_stress_0", "max_stress_1"} <= set(responses)
