# core/composition.py — a method assembled from a model and an updater.
#
# A gradient-based topology-optimisation method is two independent choices:
#
#     Model    WHAT is optimised: turns a design into an objective, a material
#              volume, the scenario's constraints, and the gradients of all of
#              them.  The physics, the filters and the sensitivity analysis
#              live here.
#     Updater  HOW the design moves: turns those numbers into the next design
#              (optimality criteria, MMA, GCMMA, ...).
#
# ComposedMethod is the glue.  It implements core.contract.OptimizationMethod,
# so the engine cannot tell a composed method from a hand-written one, and it
# fixes the one ordering that matters:
#
#     evaluation = model.evaluate(x)             objective, volume, constraints, gradients
#     model.advance(completed)                   continuation (e.g. Heaviside beta)
#     x_new = updater.update(x, evaluation, …)   may call the model's cheap parts
#     density = model.physical(x_new)            what is reported and drawn
#
# The two halves meet only through Evaluation and the Model methods below, so
# any model works with any updater — within what each can do: a composed
# method can minimise what its model can compute AND its updater can handle.
#
# A model is itself usually assembled from parts — filters, a physics engine
# (core/physics.py) and responses — see library/models/assembled.py.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

import numpy as np

from toporia.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod


@dataclass(frozen=True)
class ConstraintValue:
    """One scenario constraint at one design, normalised so that value <= 0 means satisfied.

    `value` is what the optimiser works with, which may be a smooth stand-in
    (a p-norm for a maximum).  `exact`, when the model can give it, is the same
    constraint measured exactly and normalised the same way; the engine judges
    whether a result honours its limits on `exact` when it is available.
    """
    name: str
    value: float
    gradient: np.ndarray | None
    exact: float | None = None


@dataclass(frozen=True)
class Evaluation:
    """Everything an updater needs to know about one design.

    Gradients have the shape of the design, or are None when the evaluation
    was asked for values only (Model.evaluate(x, gradients=False)).  `volume` is the total physical
    material, in the units of Model.volume_limit — the volume budget every
    method enforces.  `constraints` holds the scenario's further constraints
    in scenario order; `reported` holds extra scalars worth recording in the
    run history (a peak stress, or the compliance when it is not the objective).
    """
    objective: float
    objective_gradient: np.ndarray | None
    volume: float
    volume_gradient: np.ndarray | None
    constraints: tuple = ()
    reported: dict = field(default_factory=dict)


class Model(ABC):
    """What is optimised: a design in, objective, volume, constraints and gradients out.

    A design is an ndarray of whatever shape suits the model (the Q4 model uses
    (nely, nelx), the pyMOTO model a flat vector).  Updaters treat it
    element-wise and return the same shape.

    `capabilities.objectives` and `capabilities.constraints` list the responses
    (library.responses) the model can compute.
    """

    #: Registry key (library.models.MODELS).  An empty name means "abstract".
    name = ""
    label = ""
    order = 100
    #: Tunable parameters (core.params.Param); they become method parameters.
    params = ()
    #: Passed through to every method built on this model (see ComposedMethod).
    capabilities = Capabilities()
    #: Total material the design may use, comparable with Evaluation.volume.
    volume_limit = 0.0

    @abstractmethod
    def initialize(self, problem, solver, settings):
        """Prepare for a run.  `settings` holds this model's own Param values."""

    @abstractmethod
    def initial_design(self):
        """Return the starting design."""

    @abstractmethod
    def bounds(self):
        """Return (lower, upper) per design variable, shaped like the design."""

    @abstractmethod
    def physical(self, x):
        """Return the (nely, nelx) physical density of design x.  Cheap: no FEA."""

    @abstractmethod
    def evaluate(self, x, gradients=True):
        """Return the Evaluation of design x.  Expensive: this is the FE solve.

        With gradients=False only the values are needed (a line search, a
        gradient-free optimiser), so the sensitivity analysis may be skipped and
        the gradient fields left None.
        """

    def volume_of(self, x):
        """Total physical material of design x, without an FE solve.

        Optimality criteria calls this many times per iteration to find the
        Lagrange multiplier, which is why it must stay cheap.
        """
        return np.sum(self.physical(x))

    def advance(self, completed):
        """Called once per iteration, after evaluate: advance any continuation schedule."""


class Updater(ABC):
    """How the design moves: an Evaluation in, the next design out.

    An updater that works on a flat vector, as almost every optimiser from a
    library does, sets `flat_view = True` and builds its view with
    self.flat_problem(model) (core/flat.py): free variables only, the volume
    budget as the first constraint, both sign conventions, caching.
    """

    #: Registry key (library.updaters.UPDATERS).  An empty name means "abstract".
    name = ""
    label = ""
    order = 100
    #: Tunable parameters (core.params.Param); they become method parameters.
    params = ()
    #: Objective types the update rule is valid for; None means any.
    objectives = None
    #: How many scenario constraints it can enforce besides the volume budget;
    #: None means any number.  The conservative default is none.
    max_constraints = 0
    #: True when it works on core.flat.FlatProblem rather than on the design array.
    flat_view = False
    #: True when it runs its own loop in the background (core/external.py).
    own_loop = False
    #: The flat view's objective rescaling (see FlatProblem); None leaves it unscaled.
    flat_objective_scale = None

    def flat_problem(self, model):
        """This updater's flat view of `model`, with the declared objective scaling."""
        from toporia.framework.optimisers.flat_view import FlatProblem
        self.flat = FlatProblem(model, scale_objective_to=self.flat_objective_scale)
        return self.flat

    @abstractmethod
    def initialize(self, model, settings):
        """Prepare for a run.  `settings` holds this updater's own Param values."""

    @abstractmethod
    def update(self, x, evaluation, completed):
        """Return the next design.  `completed` counts finished iterations from 0."""

    def is_converged(self, change):
        """Optional stricter stopping criterion; see OptimizationMethod.is_converged."""
        return False

    def convergence_reason(self):
        """Why is_converged() said so, in words; None for the generic message."""
        return None

    def cached_evaluation(self, design):
        """An Evaluation of `design` the updater already has, to spare the engine a solve; or None."""
        return None

    def report(self):
        """The optimiser's own verdict (success, message, its counts) for run.json; or None."""
        return None

    def close(self):
        """Release anything still running (a background optimiser thread).  Called once, at the end."""


def _subset(settings, params):
    return {p.name: settings[p.name] for p in params}


def _combine(model_capabilities, updater):
    """A composed method can do what its model computes AND its updater handles."""
    objectives = model_capabilities.objectives
    if updater.objectives is not None:
        objectives = tuple(o for o in objectives if o in updater.objectives)
    limits = [n for n in (model_capabilities.max_constraints, updater.max_constraints) if n is not None]
    max_constraints = min(limits) if limits else None
    constraints = model_capabilities.constraints if max_constraints != 0 else ()
    if not constraints:
        objectives = tuple(o for o in objectives if o not in model_capabilities.needs_constraint)
    return replace(model_capabilities, objectives=objectives, constraints=constraints,
                   max_constraints=max_constraints)


class ComposedMethod(OptimizationMethod):
    """An OptimizationMethod made of a Model and an Updater.

    Pairings are not declared one by one: compose(model, updater) builds the
    method for any pair, named "<model>+<updater>" (e.g. "q4+mma"), and
    library.methods.method_class turns such a name into it.  A subclass may
    still be written by hand:

        class MyPairing(ComposedMethod):
            name, label = "mine", "My pairing"
            model = Q4Model
            updater = OCUpdater

    The method's parameters are the model's followed by the updater's.  Its
    capabilities are the model's, narrowed to what the updater can handle.
    """

    model = None
    updater = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.model is None or cls.updater is None:
            return
        combined = tuple(cls.model.params) + tuple(cls.updater.params)
        names = [p.name for p in combined]
        clashes = sorted({n for n in names if names.count(n) > 1})
        if clashes:
            raise TypeError(
                f"{cls.__name__}: {cls.model.__name__} and {cls.updater.__name__} both declare "
                f"{clashes}; parameter names must be unique within a method"
            )
        cls.params = combined
        cls.capabilities = _combine(cls.model.capabilities, cls.updater)

    def initialize(self, problem, solver):
        if type(self).model is None or type(self).updater is None:
            raise TypeError(f"{type(self).__name__} must set both `model` and `updater`")
        settings = self.resolve_params(solver)
        self.problem = problem
        self._model = type(self).model()
        self._updater = type(self).updater()
        self._model.initialize(problem, solver, _subset(settings, self._model.params))
        self._count_solves(self._model)
        self._updater.initialize(self._model, _subset(settings, self._updater.params))

        self.x = self._model.initial_design()
        self.density = self._model.physical(self.x)
        self.objective = np.inf
        self.change = np.inf
        self._evaluation = None

    def step(self, iteration):
        completed = iteration - 1   # continuation schedules count finished iterations
        evaluation = self._updater.cached_evaluation(self.x) or self._model.evaluate(self.x)
        self._model.advance(completed)
        x_new = self._updater.update(self.x, evaluation, completed)

        self.change = float(np.max(np.abs(x_new - self.x)))
        self.x = x_new
        self.density = self._model.physical(x_new)
        self.objective = evaluation.objective
        self._evaluation = evaluation

    def _count_solves(self, model):
        """Count every model evaluation — the engine's, and any an updater makes itself.

        Updaters differ in how many physics solves an iteration costs (GCMMA
        re-evaluates trial designs), so iterations alone do not compare them
        fairly.  The count is Toporia's own, whatever the updater reports.
        """
        self.solves = 0
        evaluate = model.evaluate

        def counted(x, gradients=True):
            self.solves += 1
            return evaluate(x, gradients=gradients)

        model.evaluate = counted

    def describe_view(self):
        """What the updater's optimiser sees, when it works on a flat view; else None."""
        flat = getattr(self._updater, "flat", None)
        return flat.describe() if flat is not None else None

    def is_converged(self):
        return self._updater.is_converged(self.change)

    def convergence_reason(self):
        return self._updater.convergence_reason()

    def report(self):
        return self._updater.report()

    def close(self):
        self._updater.close()

    def get_density(self):   return self.density
    def get_change(self):    return self.change

    def get_responses(self):
        responses = {OBJECTIVE: self.objective, "volume": float(self.density.mean()),
                     "solves": self.solves}
        if self._evaluation is not None:
            responses.update(self._evaluation.reported)
            for i, constraint in enumerate(self._evaluation.constraints):
                responses[f"constraint_{i}_{constraint.name}"] = constraint.value
                if constraint.exact is not None:
                    responses[f"constraint_{i}_{constraint.name}_exact"] = constraint.exact
        return responses


#: Separates the model from the updater in a composed method's name: "q4+mma".
SEPARATOR = "+"

_composed = {}


def compose(model_cls, updater_cls):
    """Return the method made of this model and this updater, built once per pair."""
    key = (model_cls, updater_cls)
    if key not in _composed:
        _composed[key] = type(
            f"{model_cls.__name__}_{updater_cls.__name__}", (ComposedMethod,),
            {"name": f"{model_cls.name}{SEPARATOR}{updater_cls.name}",
             "label": f"{model_cls.label} · {updater_cls.label}",
             "model": model_cls, "updater": updater_cls},
        )
    return _composed[key]


def explain(model_cls, updater_cls):
    """Plain-language reasons why this pairing offers less than one of its parts could.

    Empty when nothing is lost.  The GUI shows these next to the selectors, so a
    missing objective, constraint or filter list is explained, not just absent.
    """
    notes = []
    model = model_cls.capabilities
    combined = _combine(model, updater_cls)
    lost = [name for name in model.objectives if name not in combined.objectives]
    rule = updater_cls.objectives
    outside_rule = [name for name in lost if rule is not None and name not in rule]
    unconstrained = [name for name in lost if name not in outside_rule]
    if outside_rule:
        notes.append(f"{updater_cls.label} can only minimise {', '.join(rule)}; "
                     f"the model could also minimise {', '.join(outside_rule)}.")
    if unconstrained:
        notes.append(f"Minimising {', '.join(unconstrained)} needs a constraint besides the volume budget, "
                     f"which {updater_cls.label} cannot enforce.")
    if model.constraints and not combined.constraints:
        notes.append(f"{updater_cls.label} enforces only the volume budget, so the model's "
                     f"{', '.join(model.constraints)} constraint is not available.")
    if not model.constraints:
        notes.append(f"{model_cls.label} computes no constraint besides the volume budget.")
    if not model.accepts_filters:
        notes.append(f"{model_cls.label} filters the design itself, so the Filters list is not used.")
    return notes
