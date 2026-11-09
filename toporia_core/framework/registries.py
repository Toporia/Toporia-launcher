# framework/registries.py — one registry per kind of part, and the glue that looks parts up by name.
#
# The registries live in the core so that the core can find parts without importing
# any library.  Every source of parts is a Python entry point in the registry's group
# (toporia.methods, toporia.models, ...): Toporia's own library, toporia_library, is
# declared that way in pyproject.toml exactly as a third-party package would be, so
# the core never names it.
#
#   METHODS ... POSTPROCESSORS   the registries
#   method_class(name)           "<model>+<updater>" or a whole method -> its class
#   method_classes()             every selectable method
#   responses_for(role)          the responses that can be an objective / a constraint
#   resolve_response(spec, role) a spec -> (Response class, parameter values)
#   check_responses(scenario)    the scenario's objective and constraints, checked

from .params import resolve_params
from .parts.composition import SEPARATOR, compose
from .parts.filter import Filter
from .parts.interpolation import Interpolation
from .parts.method import OptimizationMethod
from .parts.model import Model
from .parts.postprocess import PostProcessor
from .parts.representation import Representation
from .parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response
from .parts.schedule import Schedule
from .parts.updater import Updater
from .registry import Registry

METHODS = Registry("method", OptimizationMethod, None)
MODELS = Registry("model", Model, None)
UPDATERS = Registry("updater", Updater, None)
FILTERS = Registry("filter", Filter, None)
INTERPOLATIONS = Registry("interpolation", Interpolation, None)
RESPONSES = Registry("response", Response, None)
REPRESENTATIONS = Registry("representation", Representation, None)
SCHEDULES = Registry("schedule", Schedule, None)
POSTPROCESSORS = Registry("postprocessor", PostProcessor, None)

# ── Methods ───────────────────────────────────────────────────────────────────

#: Method names from before methods were split into a model and an updater.
PRESETS = {
    "density": "q4+oc",
    "density_mma": "q4+mma",
    "mma": "q4+mma",
    "density_simpl": "q4+simpl",
    "beso": "q4+beso",
    "density_gcmma": "q4+pymoto_gcmma",
    "pymoto": "pymoto_elastic+pymoto_mma",
}


def canonical_name(name):
    """The explicit form of a method name: presets expanded, model and updater canonical."""
    return method_class(name).name


def method_class(name):
    """Return the method class for "<model>+<updater>" or a whole method's name.

    Case-insensitive; registry aliases and PRESETS are accepted.  Raises
    ValueError naming what is available for an unknown name.
    """
    key = str(name).strip().lower()
    key = PRESETS.get(key, key)
    if SEPARATOR in key:
        model, _, updater = key.partition(SEPARATOR)
        return compose(MODELS.get(model.strip()), UPDATERS.get(updater.strip()))
    try:
        return METHODS.get(key)
    except ValueError:
        raise ValueError(
            f"Unknown method {name!r}. Use '<model>{SEPARATOR}<updater>' with a model from "
            f"{MODELS.names()} and an updater from {UPDATERS.names()}, or one of {METHODS.names()}."
        ) from None


def method_classes():
    """Every selectable method: each model with each updater, then the whole methods."""
    pairs = [compose(model, updater) for model in MODELS.classes() for updater in UPDATERS.classes()]
    return pairs + METHODS.classes()


def make_method(name: str):
    """Return a new instance of the named method (either form; see method_class)."""
    return method_class(name)()


# ── Responses ─────────────────────────────────────────────────────────────────

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
    extra = {key: values.pop(key) for key in cls.structured if key in values}
    resolved = resolve_params(f"{role} {cls.name!r}", cls.params, values)
    resolved.update(extra)
    validate = getattr(cls, "validate_spec", None)
    if validate is not None:
        validate(resolved)
    return cls, resolved


def _check_variable_names(scenario, resolved):
    """Every variable a response names exists: the scenario's own, or a built-in quantity."""
    from toporia_core.framework.variables import check_variables
    specs = getattr(scenario, "variables", None) or []
    check_variables(specs)
    known = {spec["name"] for spec in specs} | {cls.name for cls in responses_for(OBJECTIVE_ROLE)}
    terms = [values for _, values in resolved]
    terms += [term for _, values in resolved for term in values.get("terms", []) or []]
    for values in terms:
        name = values.get("variable")
        if name is not None and name not in known:
            raise ValueError(f"There is no variable {name!r}; define it on the Problem page "
                             f"(the scenario's variables) or use a built-in quantity")


def check_responses(scenario):
    """Validate a scenario's objective and constraints; return them resolved.

    Returns ((objective class, values), [(constraint class, values), ...]).
    """
    objective = resolve_response(scenario.objective, OBJECTIVE_ROLE)
    constraints = [resolve_response(spec, CONSTRAINT_ROLE) for spec in scenario.constraints]
    _check_variable_names(scenario, [objective, *constraints])
    if objective[0].needs_constraint and not constraints:
        raise ValueError(
            f"Minimising {objective[0].label.lower()} needs at least one constraint besides the "
            f"volume budget (for example stress); otherwise the optimum is an empty design."
        )
    return objective, constraints


__all__ = ["METHODS", "MODELS", "UPDATERS", "FILTERS", "INTERPOLATIONS", "RESPONSES", "REPRESENTATIONS",
           "SCHEDULES", "POSTPROCESSORS", "PRESETS", "SEPARATOR", "canonical_name", "method_class",
           "method_classes", "make_method", "responses_for", "resolve_response", "check_responses",
           "CONSTRAINT_ROLE", "OBJECTIVE_ROLE"]
