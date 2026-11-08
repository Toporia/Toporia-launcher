"""plugins.responses — what a scenario can minimise or constrain.

Every Response subclass in this package with a non-empty `name` is found by the
RESPONSES registry.  Responses are declarations (see framework/parts/response.py); the
models that can compute them say so in their Capabilities.

The volume budget (scenario.volfrac) is enforced by every method and is not a
constraint entry; scenario.constraints adds further limits on top of it.

    compliance.py  weighted compliance — objective
    end_compliance.py  compliance at the final load of a non-linear solve — objective
    volume.py      material volume — objective, used with a further constraint
    stress.py      peak von Mises stress — constraint
    buckling.py    reciprocal load-factor aggregate — objective or constraint
    thermal_compliance.py  weighted thermal compliance of heat conduction — objective
    eigenfrequency.py     lowest natural frequency — objective (maximise) and constraint (at least)
    dynamic_compliance.py compliance of a harmonic load — objective
"""

# The registry and the lookups live in the core (toporia_core/framework/registries.py);
# this package is the registry's built-in source, declared in pyproject.toml.
from toporia_core.framework.registries import (
    CONSTRAINT_ROLE,
    OBJECTIVE_ROLE,
    RESPONSES,
    check_responses,
    resolve_response,
    responses_for,
)

__all__ = ["RESPONSES", "OBJECTIVE_ROLE", "CONSTRAINT_ROLE",
           "responses_for", "resolve_response", "check_responses"]
