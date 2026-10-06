"""test_physics.py — physics engines, the responses written against them, and the assembled model.

The point of the split is that a response is written once, against the
questions a physics engine answers (core/physics.py), and then works on every
engine that answers them.  These tests hold that to account: the gradients
must match finite differences, the Q4 engine must agree with pyMOTO where both
are right, and a model must offer exactly the responses its engine supports.
"""

import importlib.util

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.framework.parts.physics import ELASTIC_ENERGY, Physics
from toporia.framework.parts.response import OBJECTIVE_ROLE, Response
from toporia.framework.problem.mesh import RectangularProblem
from toporia.plugins.models.assembled import AssembledModel
from toporia.plugins.models.q4 import Q4Model
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
from toporia.plugins.problems import get_run

requires_pymoto = pytest.mark.skipif(importlib.util.find_spec("pymoto") is None,
                                     reason="optional dependency: pip install pymoto")
STRESS = {"type": "stress", "limit": 5.0, "p": 8.0, "q": 0.5, "adaptive": False}


def _model(problem="MBB Beam", m=0.3, model_cls=Q4Model, filters=(), **values):
    run = get_run(problem).updated(m=m, volfrac=0.4, filter_specs=list(filters), **values)
    model = model_cls()
    model.initialize(RectangularProblem(run.scenario, run.solver.m), run.solver, {"penal": 3.0})
    return model


def _perturbed_design(model, seed=1):
    lower, upper = model.bounds()
    rng = np.random.default_rng(seed)
    return np.clip(model.initial_design() + rng.uniform(-0.2, 0.2, lower.shape), np.maximum(lower, 0.05), upper)


def _check_gradient(value, gradient, x, free, n=8, h=1e-5, seed=2):
    """Central differences at the n free elements with the largest gradients."""
    order = np.argsort(-np.abs(gradient[free]))[:n]
    for index in np.argwhere(free)[order]:
        i, j = index
        plus, minus = x.copy(), x.copy()
        plus[i, j] += h
        minus[i, j] -= h
        fd = (value(plus) - value(minus)) / (2 * h)
        assert gradient[i, j] == pytest.approx(fd, rel=1e-4), (i, j)


# ── Gradients through the physics interface ───────────────────────────────────

@pytest.mark.parametrize("problem", ["MBB Beam", "Drone Arm"])       # one and two load cases
@pytest.mark.parametrize("filters", [(), ({"type": "density"},)], ids=["raw", "filtered"])
def test_compliance_and_stress_gradients_match_finite_differences(problem, filters):
    # "filtered-Drone Arm" is the case that caught the filter adjoint passing the
    # sensitivity of pinned elements on to their free neighbours (6 % off near holes).
    model = _model(problem, filters=filters, constraints=[dict(STRESS)])
    x = _perturbed_design(model)
    evaluation = model.evaluate(x)
    lower, upper = model.bounds()
    free = upper > lower

    _check_gradient(lambda y: model.evaluate(y).objective, evaluation.objective_gradient, x, free)
    _check_gradient(lambda y: model.evaluate(y).constraints[0].value,
                    evaluation.constraints[0].gradient, x, free)


def test_the_volume_objective_gradient_matches_finite_differences():
    model = _model(objective={"type": "volume"}, constraints=[dict(STRESS)], filters=({"type": "density"},))
    x = _perturbed_design(model)
    evaluation = model.evaluate(x)
    lower, upper = model.bounds()
    _check_gradient(lambda y: model.evaluate(y).objective, evaluation.objective_gradient, x, upper > lower)


def test_adaptive_stress_scaling_makes_the_constraint_equal_the_true_peak():
    model = _model(constraints=[{**STRESS, "adaptive": True}])
    constraint = model.evaluate(_perturbed_design(model)).constraints[0]
    assert constraint.value == pytest.approx(constraint.exact, rel=1e-12)


def test_a_gradient_is_only_computed_when_asked_for():
    model = _model(constraints=[dict(STRESS)])
    state = model.engine.solve(model.physical(_perturbed_design(model)))
    for response in (model.objective, *model.constraints):
        with_gradient, without = response.evaluate(state), response.evaluate(state, gradient=False)
        assert without.gradient is None
        assert without.value == with_gradient.value


# ── The Q4 engine against pyMOTO ──────────────────────────────────────────────

@requires_pymoto
def test_q4_and_pymoto_agree_on_compliance_and_differ_on_stress_only_by_pymotos_shear():
    """Same mesh, same design, no filtering: the displacements are the same.

    pyMOTO 2.0.1 doubles the shear stress (its strain matrix already gives the
    engineering shear and Strain(voigt=True) doubles it again).  Doubling the
    Q4 shear reproduces pyMOTO's peak exactly, which pins both the agreement
    and the one known difference.
    """
    from toporia.plugins.models.pymoto_elastic import PymotoElasticModel
    from toporia.plugins.responses.stress import VON_MISES_2D

    run = get_run("MBB Beam").updated(m=1.0, volfrac=0.5, filter_specs=[],
                                      constraints=[{"type": "stress", "limit": 1e9}])
    problem = RectangularProblem(run.scenario, run.solver.m)
    q4 = Q4Model()
    q4.initialize(problem, run.solver, {"penal": 3.0})
    pymoto = PymotoElasticModel()
    pymoto.initialize(problem, run.solver, {"penal": 3.0, "rmin": 1e-6})   # no filtering

    rng = np.random.default_rng(2)
    x = np.clip(0.5 + rng.uniform(-0.3, 0.3, (problem.nely, problem.nelx)),
                problem.lower_bound, problem.upper_bound)
    ours, theirs = q4.evaluate(x), pymoto.evaluate(x.ravel())
    assert ours.objective == pytest.approx(theirs.objective, rel=1e-9)

    stress = q4.engine.element_stress(q4.engine.solve(q4.physical(x)), 0)
    stress[..., 2] *= 2.0
    von_mises = np.sqrt(np.einsum("...i,ij,...j->...", stress, VON_MISES_2D, stress) + 1e-12)
    assert float(np.max(x ** 0.5 * von_mises)) == pytest.approx(theirs.reported["max_stress"], rel=1e-9)
    assert ours.reported["max_stress"] < theirs.reported["max_stress"]


# ── What a model offers follows from its engine ───────────────────────────────

class _EnergyOnly(Q4PlaneStress):
    """The Q4 engine, declaring only the elastic-energy feature."""
    name = "energy_only"
    provides = (ELASTIC_ENERGY,)


class _EnergyOnlyModel(AssembledModel):
    physics = _EnergyOnly


class _DeclaredOnly(Response):
    """A response no engine can compute: it does not implement evaluate()."""
    name = "declared_only"
    roles = (OBJECTIVE_ROLE,)


def test_a_model_offers_exactly_what_its_engine_provides_features_for():
    full, partial = Q4Model.capabilities, _EnergyOnlyModel.capabilities
    assert set(full.objectives) == {"compliance", "volume"} and full.constraints == ("stress",)
    assert set(partial.objectives) == {"compliance", "volume"} and partial.constraints == ()
    assert full.accepts_filters and full.needs_constraint == ("volume",)


def test_a_response_says_which_engines_it_can_compute_on():
    from toporia.plugins.responses import RESPONSES
    assert RESPONSES.get("stress").computable_on(Q4PlaneStress)
    assert not RESPONSES.get("stress").computable_on(_EnergyOnly)
    assert RESPONSES.get("volume").computable_on(Physics)        # needs no physics at all
    assert not _DeclaredOnly.computable_on(Q4PlaneStress)         # declaration only


def test_an_engine_refuses_a_question_outside_its_features():
    class Bare(Physics):
        def initialize(self, problem, settings): pass
        def solve(self, density): return None

    with pytest.raises(NotImplementedError, match="stress"):
        Bare().element_stress(None, 0)


# ── End to end: stress on Toporia's own solver ───────────────────────────────

@requires_pymoto
def test_a_stress_constraint_runs_on_the_q4_engine_with_a_constraint_capable_updater():
    run = get_run("MBB Beam").updated(method="q4+pymoto_mma", m=0.3, max_iter=4, tol=0.0,
                                      constraints=[{"type": "stress", "limit": 50.0}])
    method = initialized_method(run)
    for iteration in range(1, run.solver.max_iter + 1):
        method.step(iteration)
    responses = method.get_responses()
    assert np.isfinite(responses["max_stress"])
    assert "constraint_0_stress" in responses and "constraint_0_stress_exact" in responses
    assert np.all(np.isfinite(method.get_density()))
