"""test_composition.py — methods built from a model and an updater.

The point of the split is that any model works with any updater.  These tests
hold that promise to account by running every pairing — registered in the
method menu or not — and pin the rules the composition itself enforces.
"""

import importlib.util
import itertools
import warnings

import numpy as np
import pytest

from toporia.framework import Param
from toporia.framework.parts.composition import ComposedMethod, Model, compose
from toporia.framework.parts.method import OBJECTIVE
from toporia.framework.problem.mesh import RectangularProblem
from toporia.plugins.methods import method_class, method_classes
from toporia.plugins.models import MODELS
from toporia.plugins.models.pymoto_elastic import PymotoElasticModel
from toporia.plugins.problems import get_run
from toporia.plugins.updaters import UPDATERS
from toporia.plugins.updaters.mma import MMAUpdater
from toporia.plugins.updaters.oc import OCUpdater
from toporia.plugins.updaters.simpl import SiMPLUpdater

PAIRS = list(itertools.product(MODELS.classes(), UPDATERS.classes()))


def _require_pymoto():
    """Skip unless pyMOTO is installed, WITHOUT importing it here.

    Importing pyMOTO switches matplotlib's backend; the library imports it only
    through import_pymoto(), which undoes that, so tests must not import it directly.
    """
    if importlib.util.find_spec("pymoto") is None:
        pytest.skip("optional dependency: pip install pymoto")


def _needs_pymoto(*classes):
    return any(cls.name.startswith("pymoto") for cls in classes)


def _compose(model_cls, updater_cls):
    return type(f"{model_cls.__name__}_{updater_cls.__name__}", (ComposedMethod,),
                {"model": model_cls, "updater": updater_cls})


def test_any_pair_is_named_model_plus_updater_and_built_once():
    for model_cls, updater_cls in PAIRS:
        cls = method_class(f"{model_cls.name}+{updater_cls.name}")
        assert (cls.model, cls.updater) == (model_cls, updater_cls)
        assert cls is compose(model_cls, updater_cls)


def _run(method_cls, problem="MBB Beam", iterations=3, **values):
    run = get_run(problem).updated(m=0.3, max_iter=iterations, tol=0.0, **values)
    method = method_cls()
    method.initialize(RectangularProblem(run.scenario, run.solver.m), run.solver)
    try:
        for iteration in range(1, iterations + 1):
            method.step(iteration)
    finally:
        method.close()   # an updater may run its optimiser in a background thread
    return method


@pytest.mark.parametrize("cls", [c for c in method_classes() if issubclass(c, ComposedMethod)],
                         ids=lambda c: c.name)
def test_a_registered_method_is_the_sum_of_its_parts(cls):
    assert cls.params == tuple(cls.model.params) + tuple(cls.updater.params)
    method, model, updater = cls.capabilities, cls.model.capabilities, cls.updater
    assert (method.variable_kind, method.accepts_filters) == (model.variable_kind, model.accepts_filters)
    # A composed method can do what its model computes AND its updater handles.
    assert set(method.objectives) <= set(model.objectives)
    assert set(method.constraints) <= set(model.constraints)
    if updater.max_constraints == 0:
        assert method.constraints == ()


def test_a_parameter_clash_between_model_and_updater_is_rejected():
    class ClashingModel(Model):
        params = (Param("move", 0.5),)   # the OC updater also declares "move"

    with pytest.raises(TypeError, match="move"):
        _compose(ClashingModel, OCUpdater)


@pytest.mark.parametrize(("model_cls", "updater_cls"), PAIRS,
                         ids=[f"{m.name}+{u.name}" for m, u in PAIRS])
def test_every_model_works_with_every_updater(model_cls, updater_cls):
    if _needs_pymoto(model_cls, updater_cls):
        _require_pymoto()
    method = _run(_compose(model_cls, updater_cls))

    density = method.get_density()
    assert density.shape == (6, 18)
    assert np.all(np.isfinite(density))
    assert density.min() >= -1e-9 and density.max() <= 1 + 1e-9
    assert np.isfinite(method.get_responses()[OBJECTIVE])
    assert np.isfinite(method.get_change())


def test_oc_survives_elements_whose_volume_gradient_is_zero():
    """pyMOTO zeroes the adjoint of pinned elements, so inside a hole dV/dx is 0.

    OC divides by that gradient; this pairing on a problem with holes is the
    case that used to produce NaNs.
    """
    _require_pymoto()
    method = _run(_compose(PymotoElasticModel, OCUpdater), problem="Drone Arm", volfrac=0.4)
    assert np.all(np.isfinite(method.get_density()))


def test_pyMOTO_is_given_only_the_free_variables():
    """Pinned elements have equal bounds, and pyMOTO's MMA divides by that range.

    Before the split this raised divide-by-zero warnings on any problem with
    holes; handing pyMOTO only the free variables removes them.
    """
    _require_pymoto()
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        method = _run(method_class("pymoto"), problem="Drone Arm", volfrac=0.4)
    problem = method.problem
    density = method.get_density()
    assert np.all(density[problem.void_elements] < 1e-6)
    assert np.all(density[problem.passive_elements] > 1 - 1e-6)


def test_simpl_keeps_every_iterate_inside_the_bounds_without_clipping():
    """The sigmoid maps the reals into (0, 1), so no iterate can leave the box.

    Checked on a problem with holes, where the bounds are not 0 and 1 everywhere.
    """
    method = _run(method_class("density_simpl"), problem="Drone Arm", iterations=5, volfrac=0.4)
    problem = method.problem
    assert np.all(method.x >= problem.lower_bound - 1e-12)
    assert np.all(method.x <= problem.upper_bound + 1e-12)


def test_simpl_shrinks_its_step_when_the_objective_stops_improving():
    updater = SiMPLUpdater()
    updater.step, updater.growth, updater.step_cap, updater.step_floor = 1.0, 2.0, 100.0, 1e-3
    updater._previous_objective = None
    assert updater._adapt(10.0) == 1.0     # first call: nothing to compare against
    assert updater._adapt(9.0) == 2.0      # improved, so grow
    assert updater._adapt(9.5) == 1.0      # worse, so halve


def test_beso_designs_are_binary_and_respect_the_volume_budget():
    """Every element is at the void density or solid, and the budget still holds."""
    method = _run(method_class("beso"), iterations=40, volfrac=0.5)
    x = method.x
    void = method._updater.void_density
    interior = (x > void + 1e-9) & (x < 1.0 - 1e-9)
    assert not np.any(interior), f"{int(np.sum(interior))} elements are neither void nor solid"
    assert method.get_density().mean() <= 0.5 + 1e-6


def test_beso_does_not_declare_convergence_while_it_is_still_shedding_volume():
    """A run must never be called converged before it has reached its budget.

    Starting from the full domain at a 2% evolution rate, 40% is many iterations
    away, so the objective-based criterion must stay silent however flat the
    objective happens to look.
    """
    method = _run(method_class("beso"), iterations=12, volfrac=0.4)
    assert method._updater.target > method._updater.limit
    assert not method.is_converged()


def test_the_mma_updater_adds_its_own_stricter_tolerance():
    updater = MMAUpdater()
    updater.convtol = 1e-4
    assert updater.is_converged(5e-5)
    assert not updater.is_converged(1e-3)
