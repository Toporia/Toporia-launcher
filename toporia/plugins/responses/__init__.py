"""plugins.responses — what a scenario can minimise or constrain.

Every Response subclass in this package with a non-empty `name` is found by the
RESPONSES registry.  Responses are declarations (see framework/parts/response.py); the
models that can compute them say so in their Capabilities.

The volume budget (scenario.volfrac) is enforced by every method and is not a
constraint entry; scenario.constraints adds further limits on top of it.

    compliance.py  weighted compliance — objective
    volume.py      material volume — objective, used with a further constraint
    stress.py      peak von Mises stress — constraint
"""

from toporia.framework.params import resolve_params
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response
from toporia.framework.registry import Registry

RESPONSES = Registry("response", Response, __name__)


def responses_for(role):
    """All responses that can play `role`, in menu order."""
    return [cls for cls in RESPONSES.classes() if role in cls.roles]


def resolve_response(spec, role):
    """Return (Response class, parameter values) for one objective or constraint spec.

    Raises ValueError for an unknown type, a response used in a role it cannot
    play, or a parameter the response does not declare.
    """
    values = dict(spec)
    kind = values.pop("type", "compliance" if role == OBJECTIVE_ROLE else None)
    if kind is None:
        raise ValueError(f"Every {role} needs a 'type', got {dict(spec)}")
    cls = RESPONSES.get(kind)
    if role not in cls.roles:
        roles = " or ".join(cls.roles) or "nothing"
        raise ValueError(f"{cls.label!r} cannot be used as the {role}; it can be used as: {roles}")
    return cls, resolve_params(f"{role} {cls.name!r}", cls.params, values)


def check_responses(scenario):
    """Validate a scenario's objective and constraints; return them resolved.

    Returns ((objective class, values), [(constraint class, values), ...]).
    """
    objective = resolve_response(scenario.objective, OBJECTIVE_ROLE)
    constraints = [resolve_response(spec, CONSTRAINT_ROLE) for spec in scenario.constraints]
    if objective[0].needs_constraint and not constraints:
        raise ValueError(
            f"Minimising {objective[0].label.lower()} needs at least one constraint besides the "
            f"volume budget (for example stress); otherwise the optimum is an empty design."
        )
    return objective, constraints


__all__ = ["RESPONSES", "OBJECTIVE_ROLE", "CONSTRAINT_ROLE",
           "responses_for", "resolve_response", "check_responses"]
