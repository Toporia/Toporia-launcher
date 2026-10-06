# framework/parts/model.py — WHAT is optimised: a design in, numbers and gradients out.
#
# A Model turns a design into an Evaluation: the objective, the material
# volume, the scenario's further constraints, and the gradient of each.  The
# physics, the filters and the sensitivity analysis live behind it; an
# Updater (updater.py) only ever sees the Evaluation.
#
# Most models are not written by hand: plugins/models/assembled.py joins
# filters, a physics engine (physics.py) and responses (response.py) into one.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from toporia.framework.parts.method import Capabilities


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
    (plugins.responses) the model can compute.
    """

    #: Registry key (plugins.models.MODELS).  An empty name means "abstract".
    name = ""
    label = ""
    order = 100
    #: Tunable parameters (framework.params.Param); they become method parameters.
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

    def set_parameter(self, path, value):
        """Change the value at a parameter path during a run (a schedule).  None can by default."""
        raise ValueError(f"{self.label or type(self).__name__} cannot change {path!r} during a run")

    def continuing(self):
        """True while a continuation of the model's own (a filter's) is still moving."""
        return False

    def geometry(self, x):
        """Explicit outlines of design x (closed polygons in mm), when its variables describe shapes; else None."""
        return None

    def advance(self, completed):
        """Called once per iteration, after evaluate: advance any continuation schedule."""
