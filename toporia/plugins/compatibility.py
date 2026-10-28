"""plugins.compatibility — what a part works with, and which presets show it, for its help.

Every part already declares what it can do: its dimensions, the objectives and
constraints a model computes, whether a model honours filters, a material law or
a design representation, which updaters need one density per element, and so
on.  This module reads those declarations and says them in plain sentences, so
the "?" window of every part can answer "when can I use this, and with what?"
without anyone writing (and forgetting to update) a compatibility list by hand.

    function_id(cls)        "filter:heaviside", "model:q4", "method:q4+oc", ...
    use_when(cls)           when to choose it (its own `use_when`; a composed method joins its two parts')
    works_with(cls)         [sentence, ...]  what it combines with, and what it refuses
    demo_presets(fid)       presets that exercise it, dedicated research presets first
    part_class(fid)         the registered class behind an id

Nothing here imports Qt; the GUI's help window and the docs can both use it.
"""

from functools import lru_cache

from toporia.framework.parts.filter import Filter
from toporia.framework.parts.interpolation import Interpolation
from toporia.framework.parts.method import OptimizationMethod
from toporia.framework.parts.model import Model
from toporia.framework.parts.postprocess import PostProcessor
from toporia.framework.parts.representation import Representation
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response
from toporia.framework.parts.schedule import Schedule
from toporia.framework.parts.updater import Updater

KINDS = ((Filter, "filter"), (Interpolation, "interpolation"), (Representation, "representation"),
         (Response, "response"), (Schedule, "schedule"), (PostProcessor, "postprocessor"),
         (Updater, "updater"), (Model, "model"), (OptimizationMethod, "method"))
#: How many names a sentence lists before it says "and N more".
LISTED = 8


def function_id(cls):
    """The part's id as the research census writes it, e.g. "filter:heaviside"; "" for an unknown class."""
    for base, kind in KINDS:
        if isinstance(cls, type) and issubclass(cls, base):
            return f"{kind}:{cls.name}"
    return ""


def part_class(fid):
    """The registered class for an id such as "filter:heaviside"; None for physics engines and unknown ids."""
    from toporia.plugins.filters import FILTERS
    from toporia.plugins.interpolations import INTERPOLATIONS
    from toporia.plugins.methods import METHODS
    from toporia.plugins.models import MODELS
    from toporia.plugins.postprocessors import POSTPROCESSORS
    from toporia.plugins.representations import REPRESENTATIONS
    from toporia.plugins.responses import RESPONSES
    from toporia.plugins.schedules import SCHEDULES
    from toporia.plugins.updaters import UPDATERS
    registries = {"filter": FILTERS, "interpolation": INTERPOLATIONS, "representation": REPRESENTATIONS,
                  "response": RESPONSES, "schedule": SCHEDULES, "postprocessor": POSTPROCESSORS,
                  "updater": UPDATERS, "model": MODELS, "method": METHODS}
    kind, _, name = fid.partition(":")
    try:
        return registries[kind].get(name)
    except (KeyError, ValueError):
        return None


def _names(items):
    """Labels separated by semicolons, since several labels contain commas themselves."""
    items = list(items)
    if len(items) > LISTED:
        return "; ".join(items[:LISTED]) + f"; and {len(items) - LISTED} more"
    return "; ".join(items)


def _dims(dims):
    if dims is None:
        return "Works in 2-D and 3-D."
    return {(2,): "2-D only.", (3,): "3-D only."}.get(tuple(dims), "Works in 2-D and 3-D.")


def _models():
    from toporia.plugins.models import MODELS
    return MODELS.classes()


def _updaters():
    from toporia.plugins.updaters import UPDATERS
    return UPDATERS.classes()


def _labels(classes):
    return [c.label or c.name for c in classes]


def _compose(model, updater):
    from toporia.framework.parts.composition import compose
    return compose(model, updater)


def _pairs_with(model=None, updater=None):
    """The partners a model (or updater) forms a usable method with: at least one objective, a shared dimension."""
    partners = []
    for other in (_updaters() if model is not None else _models()):
        m, u = (model, other) if model is not None else (other, updater)
        caps = _compose(m, u).capabilities
        shared = u.dims is None or set(u.dims) & set(caps.dims)
        if caps.objectives and shared:
            partners.append(other)
    return partners


def _model_lines(cls):
    caps = cls.capabilities
    lines = [_dims(caps.dims),
             "Objectives it can compute: " + (", ".join(caps.objectives) or "none") + ".",
             "Constraints it can compute: " + (", ".join(caps.constraints) or "only the volume budget") + "."]
    honours = [what for what, flag in (("filters", caps.accepts_filters), ("a material law", caps.accepts_interpolation),
                                       ("a design representation", caps.accepts_representation)) if flag]
    ignores = [what for what, flag in (("filters", caps.accepts_filters), ("a material law", caps.accepts_interpolation),
                                       ("a design representation", caps.accepts_representation)) if not flag]
    if honours:
        lines.append("Uses the chosen " + ", ".join(honours) + ".")
    if ignores:
        lines.append("Does not use " + ", ".join(ignores) + "; those choices are disabled with it.")
    if caps.supports_springs:
        lines.append("Supports point springs (mechanisms).")
    partners = _pairs_with(model=cls)
    lines.append(f"Pairs with {len(partners)} updaters: {_names(_labels(partners))}.")
    return lines


def _updater_lines(cls):
    lines = [_dims(cls.dims)]
    if cls.objectives is not None:
        lines.append("Objectives it can minimise: " + ", ".join(cls.objectives) + ".")
    if cls.max_constraints == 0:
        lines.append("Enforces the volume budget only; no further constraints.")
    else:
        count = "any number of" if cls.max_constraints is None else f"up to {cls.max_constraints}"
        kinds = "any type" if cls.constraints is None else ", ".join(cls.constraints)
        lines.append(f"Enforces the volume budget plus {count} further constraint(s) ({kinds}).")
    if cls.needs_element_densities:
        lines.append("Needs one density per element: refused with any other design representation.")
    if cls.own_loop:
        lines.append("Runs its own optimisation loop in the background (an external library).")
    partners = _pairs_with(updater=cls)
    lines.append(f"Pairs with {len(partners)} models: {_names(_labels(partners))}.")
    return lines


def _users(flag):
    """Models whose capabilities honour `flag` (accepts_filters, ...)."""
    return [m for m in _models() if getattr(m.capabilities, flag)]


def _filter_lines(cls):
    lines = [_dims(cls.dims)]
    lines.append("Exact adjoint (checked against finite differences)." if cls.exact_adjoint else
                 "Heuristic: its backward pass is not the exact derivative, so gradient checks skip it.")
    if cls.must_be_last:
        lines.append("Must be the last filter in the chain: a later filter would break its geometric meaning.")
    if cls.schedulable:
        lines.append("A continuation schedule can drive: " + ", ".join(cls.schedulable) + ".")
    lines.append("Used by models that accept filters: " + _names(_labels(_users("accepts_filters"))) + ".")
    return lines


def _interpolation_lines(cls):
    lines = [_dims(cls.dims)]
    if cls.nonlinear_volume:
        lines.append("Its material cost differs from the plain density sum, so the volume budget counts effective material.")
    if cls.schedulable:
        lines.append("A continuation schedule can drive: " + ", ".join(cls.schedulable) + ".")
    lines.append("Used by models that accept a material law: " + _names(_labels(_users("accepts_interpolation"))) + ".")
    return lines


def _representation_lines(cls):
    lines = [_dims(cls.dims)]
    if cls.element_wise:
        lines.append("One variable per element, so every updater works with it.")
    else:
        refused = [u for u in _updaters() if u.needs_element_densities]
        lines.append("Not with element-only updaters: " + _names(_labels(refused)) + ".")
    lines.append("Used by models that accept a representation: "
                 + _names(_labels(_users("accepts_representation"))) + ".")
    if cls.advice:
        lines.append("Advice: " + cls.advice)
    return lines


def _response_lines(cls):
    roles = [r for r in (OBJECTIVE_ROLE, CONSTRAINT_ROLE) if r in cls.roles]
    lines = [_dims(cls.dims), "Can be used as: " + (" and ".join(roles) or "neither (report only)") + "."]
    if cls.needs_constraint:
        lines.append("Only meaningful as an objective together with a further constraint.")
    as_objective = [m for m in _models() if cls.name in m.capabilities.objectives]
    as_constraint = [m for m in _models() if cls.name in m.capabilities.constraints]
    if OBJECTIVE_ROLE in roles:
        lines.append("Models that compute it as objective: " + (_names(_labels(as_objective)) or "none") + ".")
    if CONSTRAINT_ROLE in roles:
        lines.append("Models that compute it as constraint: " + (_names(_labels(as_constraint)) or "none") + ".")
        only = getattr(cls, "only_with_updaters", ())
        enforcing = [u for u in _updaters() if u.max_constraints != 0
                     and (u.constraints is None or cls.name in u.constraints)
                     and (not only or u.name in only)]
        lines.append("Updaters that can enforce it: " + (_names(_labels(enforcing)) or "none") + ".")
    return lines


def _schedule_lines(cls):
    from toporia.plugins.filters import FILTERS
    from toporia.plugins.interpolations import INTERPOLATIONS
    driven = [f"{c.label}: {', '.join(c.schedulable)}" for registry in (FILTERS, INTERPOLATIONS)
              for c in registry.classes() if c.schedulable]
    driven += [f"{c.label}: {', '.join(c.schedulable)}" for c in _models() + _updaters()
               if getattr(c, "schedulable", ())]
    return [_dims(cls.dims), "Drives one parameter path during a run. Parameters that can be scheduled: "
            + "; ".join(driven) + "."]


def _postprocessor_lines(cls):
    lines = [_dims(cls.dims), "Runs after the optimisation on the finished design; it does not change the run."]
    if cls.dependencies:
        lines.append("Needs: " + ", ".join(cls.dependencies) + ".")
    return lines


def _method_lines(cls):
    caps = cls.capabilities
    lines = [_dims(caps.dims),
             "Objectives: " + (", ".join(caps.objectives) or "none") + ".",
             "Constraints besides the volume budget: " + (", ".join(caps.constraints) or "none") + "."]
    flags = (("filters", caps.accepts_filters), ("a material law", caps.accepts_interpolation),
             ("a design representation", caps.accepts_representation))
    lines.append("Uses " + (", ".join(what for what, flag in flags if flag) or "none of filters, material law or representation")
                 + ".")
    updater = getattr(cls, "updater", None)
    if updater is not None and updater.needs_element_densities:
        lines.append(f"{updater.label} needs one density per element, so only the element-density representation works.")
    if updater is not None and updater.dims is not None and not set(updater.dims) & set(caps.dims):
        lines.append(f"Not usable: {updater.label} does not work in the model's dimensions.")
    return lines


LINES = {"model": _model_lines, "updater": _updater_lines, "filter": _filter_lines,
         "interpolation": _interpolation_lines, "representation": _representation_lines,
         "response": _response_lines, "schedule": _schedule_lines, "postprocessor": _postprocessor_lines,
         "method": _method_lines}


def use_when(cls):
    """When to choose the part, as its own `use_when` says; a composed method joins its model's and updater's."""
    own = getattr(cls, "use_when", "")
    if own:
        return own
    parts = [getattr(cls, part, None) for part in ("model", "updater")]
    return "\n".join(f"{sub.label}: {sub.use_when}" for sub in parts if sub is not None and sub.use_when)


def works_with(cls):
    """Plain sentences on where the part can be used and what it refuses; [] for an unknown class."""
    fid = function_id(cls)
    if not fid:
        return []
    try:
        return LINES[fid.split(":", 1)[0]](cls)
    except Exception as error:   # a help window must open even if a plugin declares something odd
        return [f"(Compatibility could not be worked out: {error})"]


@lru_cache(maxsize=1)
def _preset_functions():
    from toporia.plugins.problems import problem_description, problem_names
    found = {}
    for name in problem_names():
        try:
            description = problem_description(name)
        except Exception:
            continue
        for function in getattr(description, "functions", ()):
            found.setdefault(function, []).append(name)
    return found


def demo_presets(fid):
    """Presets that exercise `fid`: dedicated research and paper presets first, then general ones."""
    if fid.startswith("method:") and "+" in fid:
        model, updater = fid[len("method:"):].split("+", 1)
        names = set(_preset_functions().get("model:" + model, ())) & set(_preset_functions().get("updater:" + updater, ()))
    else:
        names = set(_preset_functions().get(fid, ()))
    dedicated = sorted(n for n in names if n.startswith(("Research:", "Paper:")))
    return dedicated + sorted(names - set(dedicated))
