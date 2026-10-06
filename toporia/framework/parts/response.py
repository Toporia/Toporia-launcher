# framework/parts/response.py — the quantities a scenario can minimise or constrain.
#
# A Response is first a declaration: a name, a label, the roles it can play,
# and its parameters.  Scenarios refer to responses by name:
#
#     objective   = {"type": "compliance"}
#     constraints = [{"type": "stress", "limit": 10.0, "p": 8}]
#
# From these declarations the GUI builds its objective and constraint panels,
# sweeps can vary their numeric parameters, and a run validates them before it
# starts.
#
# A Response can also compute itself, against the questions a physics engine
# answers (framework/parts/physics.py).  Such a response lists the engine features it
# `requires`, and then works with every engine that provides them:
#
#     response.setup(physics, problem, settings)            once per run
#     response.evaluate(state, gradient=True) -> ResponseValue
#
# A response that cannot be computed this way (`requires = None`) is only
# available through a model that computes it itself, as the pyMOTO model does.

from dataclasses import dataclass, field

import numpy as np

OBJECTIVE_ROLE = "objective"
CONSTRAINT_ROLE = "constraint"


@dataclass(frozen=True)
class ResponseValue:
    """One response at one design.

    value     : what the optimiser works with.  As a constraint it is normalised
                so that value <= 0 means satisfied (framework.parts.composition.ConstraintValue).
    gradient  : d(value)/d(physical density), shaped like the density;
                None when it was not requested.
    exact     : for a constraint whose value is a smooth stand-in (a p-norm for
                a maximum), the same constraint measured exactly; else None.
    reported  : extra scalars worth recording in the run history.
    """
    value: float
    gradient: np.ndarray | None = None
    exact: float | None = None
    reported: dict = field(default_factory=dict)


class Response:
    """Declaration of one quantity a scenario can minimise or constrain."""

    #: Registry key used in specs: {"type": name, ...}.  Empty = abstract.
    name = ""
    #: Human-readable name for menus.
    label = ""
    #: Menu position; lower comes first.
    order = 100
    #: Which of OBJECTIVE_ROLE / CONSTRAINT_ROLE this response can play.
    roles = ()
    #: Tunable parameters (framework.params.Param), e.g. a constraint's limit.
    params = ()
    #: True when minimising this response is meaningless without a further
    #: constraint (minimising volume alone gives an empty design).
    needs_constraint = False
    #: Printed at the start of every run that uses this response as the
    #: objective: practical guidance the declaration alone cannot enforce.
    advice = ""
    #: Physics features (framework.parts.physics) evaluate() needs.  () means it needs
    #: none — it is computed from the density alone.  None means it cannot
    #: compute itself and only a model that computes it can offer it.
    requires = None
    #: Parameter values for checking the gradient against finite differences
    #: (toporia.checks), when the defaults make the gradient deliberately inexact.
    gradient_check_settings = {}

    @classmethod
    def computable_on(cls, physics):
        """True when this response can compute itself on the given physics class."""
        return cls.requires is not None and set(cls.requires) <= set(physics.provides)

    def setup(self, physics, problem, settings):
        """Prepare for a run on `physics`.  `settings` holds this response's Param values."""
        self.physics = physics
        self.problem = problem
        self.settings = settings

    def evaluate(self, state, gradient=True):
        """Return the ResponseValue for a solved state.  Skip the gradient when not asked for it."""
        raise NotImplementedError(f"Response {self.name!r} does not compute itself")
