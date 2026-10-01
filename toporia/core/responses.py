# core/responses.py — the quantities a scenario can minimise or constrain.
#
# A Response is a declaration, not a computation: a name, a label, the roles it
# can play, and its parameters.  Scenarios refer to responses by name:
#
#     objective   = {"type": "compliance"}
#     constraints = [{"type": "stress", "limit": 10.0, "p": 8}]
#
# From these declarations the GUI builds its objective and constraint panels,
# sweeps can vary their numeric parameters, and a run validates them before it
# starts.  How a response is *computed* belongs to the model, because the
# sensitivity analysis is specific to its physics; each model lists the
# responses it can compute in its Capabilities.

OBJECTIVE_ROLE = "objective"
CONSTRAINT_ROLE = "constraint"


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
    #: Tunable parameters (core.params.Param), e.g. a constraint's limit.
    params = ()
    #: True when minimising this response is meaningless without a further
    #: constraint (minimising volume alone gives an empty design).
    needs_constraint = False
    #: Printed at the start of every run that uses this response as the
    #: objective: practical guidance the declaration alone cannot enforce.
    advice = ""
