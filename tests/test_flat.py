"""test_flat.py — the problem as an optimisation library sees it (core/flat.py).

Every adapter for an outside optimiser relies on this view, so it is pinned
here once: the translation between design and vector, the volume budget as
g_0, both sign conventions, the objective scaling, and the solve count that
caching is meant to keep down.
"""

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.framework.optimisers.flat_view import VOLUME_BUDGET, FlatProblem
from toporia.framework.problem.mesh import RectangularProblem
from toporia.plugins.models.q4 import Q4Model
from toporia.plugins.problems import get_run

STRESS = {"type": "stress", "limit": 5.0}


def _model(problem="Drone Arm", **values):
    run = get_run(problem).updated(m=0.3, volfrac=0.4, **values)
    model = Q4Model()
    model.initialize(RectangularProblem(run.scenario, run.solver.m), run.solver, {"penal": 3.0})
    return model


class _Counting:
    """Wraps a model and counts its evaluations, with and without gradients."""

    def __init__(self, model):
        self.model, self.calls = model, []

    def __getattr__(self, name):
        return getattr(self.model, name)

    def evaluate(self, x, gradients=True):
        self.calls.append(gradients)
        return self.model.evaluate(x, gradients=gradients)


# ── Translation ───────────────────────────────────────────────────────────────

def test_only_the_free_variables_are_handed_over_and_fixed_ones_come_back_at_their_bounds():
    model = _model()
    flat = FlatProblem(model)
    lower, upper = model.bounds()
    fixed = upper <= lower
    assert fixed.any()                                  # the drone arm has holes and rings
    assert flat.n == int(np.sum(~fixed)) and flat.n_fixed == int(np.sum(fixed))
    assert np.all(flat.upper > flat.lower)              # no zero-width bounds reach the optimiser

    x = np.linspace(0.0, 1.0, flat.n)
    design = flat.expand(x)
    assert design.shape == lower.shape
    assert np.array_equal(design[fixed], lower[fixed])
    assert np.array_equal(flat.reduce(design), x)
    assert np.array_equal(flat.reduce(model.initial_design()), flat.x0)


def test_the_column_major_order_matches_top88():
    model = _model("MBB Beam")
    flat = FlatProblem(model)
    design = np.arange(np.prod(model.bounds()[0].shape), dtype=float).reshape(model.bounds()[0].shape)
    assert np.array_equal(flat.reduce(design), design.reshape(-1, order="F"))


# ── The callbacks ─────────────────────────────────────────────────────────────

def test_f_g_and_their_gradients_are_the_models_numbers_with_the_volume_budget_first():
    model = _model(constraints=[dict(STRESS)])
    flat = FlatProblem(model)
    x = flat.x0
    evaluation = model.evaluate(flat.expand(x))

    assert flat.f(x) == evaluation.objective
    assert np.array_equal(flat.df(x), flat.reduce(evaluation.objective_gradient))
    g = flat.g(x)
    assert g[0] == pytest.approx(evaluation.volume / model.volume_limit - 1.0)
    assert g[1] == evaluation.constraints[0].value
    dg = flat.dg(x)
    assert dg.shape == (2, flat.n)
    assert np.allclose(dg[0], flat.reduce(evaluation.volume_gradient) / model.volume_limit)
    assert flat.constraint_names == [VOLUME_BUDGET, "stress"] and flat.m == 2


def test_both_sign_conventions_are_offered():
    flat = FlatProblem(_model(constraints=[dict(STRESS)]))
    x = flat.x0
    assert np.array_equal(flat.g_geq(x), -flat.g(x))
    assert np.array_equal(flat.dg_geq(x), -flat.dg(x))


def test_the_objective_is_scaled_once_from_its_first_value():
    flat = FlatProblem(_model(), scale_objective_to=10.0)
    assert flat.f(flat.x0) == pytest.approx(10.0)
    scale = flat.objective_scale
    x = np.clip(flat.x0 + 0.1, flat.lower, flat.upper)
    flat.f(x)
    assert flat.objective_scale == scale                 # fixed: the problem must not drift
    assert np.allclose(flat.df(x), scale * flat.reduce(flat.evaluation(x).objective_gradient))


# ── Caching and gradients on request ──────────────────────────────────────────

def test_asking_for_everything_at_one_point_costs_one_solve():
    counting = _Counting(_model(constraints=[dict(STRESS)]))
    flat = FlatProblem(counting)
    x = flat.x0
    flat.f(x), flat.g(x), flat.df(x), flat.dg(x), flat.g_geq(x)
    assert counting.calls == [True]
    assert (flat.evaluations, flat.gradient_evaluations) == (1, 1)


def test_a_gradient_free_optimiser_never_pays_for_gradients():
    counting = _Counting(_model())
    flat = FlatProblem(counting, values_with_gradients=False)
    for shift in (0.0, 0.05, 0.1):
        x = np.clip(flat.x0 + shift, flat.lower, flat.upper)
        flat.f(x), flat.g(x)
    assert counting.calls == [False, False, False]
    flat.df(x)                                          # asked for at last: one more solve
    assert counting.calls[-1] is True and flat.gradient_evaluations == 1


def test_a_remembered_evaluation_is_reused():
    model = _model()
    counting = _Counting(model)
    flat = FlatProblem(counting)
    design = model.initial_design()
    flat.remember(design, model.evaluate(design))
    x = flat.reduce(design)
    flat.f(x), flat.df(x), flat.g(x), flat.dg(x)
    assert counting.calls == []


# ── Seen from a run ───────────────────────────────────────────────────────────

def test_a_run_counts_its_solves_and_says_what_the_optimiser_sees(capsys):
    run = get_run("Drone Arm").updated(method="q4+mma", m=0.3, max_iter=3, tol=0.0)
    method = initialized_method(run)
    for iteration in range(1, 4):
        method.step(iteration)
    assert method.get_responses()["solves"] == 3            # MMA: one solve per iteration
    out = capsys.readouterr().out
    assert "optimiser sees:" in out and "free variables" in out and "fixed, left out" in out
