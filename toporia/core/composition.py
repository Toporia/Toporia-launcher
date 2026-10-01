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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

import numpy as np

from .contract import OBJECTIVE, Capabilities, OptimizationMethod


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
    gradient: np.ndarray
    exact: float | None = None


@dataclass(frozen=True)
class Evaluation:
    """Everything an updater needs to know about one design.

    Gradients have the shape of the design.  `volume` is the total physical
    material, in the units of Model.volume_limit — the volume budget every
    method enforces.  `constraints` holds the scenario's further constraints
    in scenario order; `reported` holds extra scalars worth recording in the
    run history (a peak stress, or the compliance when it is not the objective).
    """
    objective: float
    objective_gradient: np.ndarray
    volume: float
    volume_gradient: np.ndarray
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
    def evaluate(self, x):
        """Return the Evaluation of design x.  Expensive: this is the FE solve."""

    def volume_of(self, x):
        """Total physical material of design x, without an FE solve.

        Optimality criteria calls this many times per iteration to find the
        Lagrange multiplier, which is why it must stay cheap.
        """
        return np.sum(self.physical(x))

    def advance(self, completed):
        """Called once per iteration, after evaluate: advance any continuation schedule."""


class Updater(ABC):
    """How the design moves: an Evaluation in, the next design out."""

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

    @abstractmethod
    def initialize(self, model, settings):
        """Prepare for a run.  `settings` holds this updater's own Param values."""

    @abstractmethod
    def update(self, x, evaluation, completed):
        """Return the next design.  `completed` counts finished iterations from 0."""

    def is_converged(self, change):
        """Optional stricter stopping criterion; see OptimizationMethod.is_converged."""
        return False


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
    return replace(model_capabilities, objectives=objectives, constraints=constraints,
                   max_constraints=max_constraints)


class ComposedMethod(OptimizationMethod):
    """An OptimizationMethod made of a Model and an Updater.

    Subclasses set two class attributes and nothing else:

        class DensityOC(ComposedMethod):
            name, label = "density", "SIMP density (OC)"
            model = Q4ComplianceModel
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
        self._updater.initialize(self._model, _subset(settings, self._updater.params))

        self.x = self._model.initial_design()
        self.density = self._model.physical(self.x)
        self.objective = np.inf
        self.change = np.inf
        self._evaluation = None

    def step(self, iteration):
        completed = iteration - 1   # continuation schedules count finished iterations
        evaluation = self._model.evaluate(self.x)
        self._model.advance(completed)
        x_new = self._updater.update(self.x, evaluation, completed)

        self.change = float(np.max(np.abs(x_new - self.x)))
        self.x = x_new
        self.density = self._model.physical(x_new)
        self.objective = evaluation.objective
        self._evaluation = evaluation

    def is_converged(self):
        return self._updater.is_converged(self.change)

    def get_density(self):   return self.density
    def get_change(self):    return self.change

    def get_responses(self):
        responses = {OBJECTIVE: self.objective, "volume": float(self.density.mean())}
        if self._evaluation is not None:
            responses.update(self._evaluation.reported)
            for i, constraint in enumerate(self._evaluation.constraints):
                responses[f"constraint_{i}_{constraint.name}"] = constraint.value
                if constraint.exact is not None:
                    responses[f"constraint_{i}_{constraint.name}_exact"] = constraint.exact
        return responses
