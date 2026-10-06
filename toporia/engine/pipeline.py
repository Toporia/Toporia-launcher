# engine/pipeline.py — what a run is made of, in words.
#
# A run's method is assembled from parts: the design passes through the
# filters, the physics engine solves it, the responses are measured, and the
# updater moves the design.  This module names each part for a given Run, so
# the console and the GUI show exactly the same chain:
#
#     variables -> representation -> filters -> physics (material law) -> objective, constraints -> updater
#
# Whole methods (the RBF level set) do not split into parts; for those the
# chain is the method itself.
#
# pipeline_parts() is the one answer to "which plugins does this run use": the
# console line, the GUI's Pipeline box, run.json's record of every part and
# the Check Parts mode all start from it.  A part that comes from another
# installed package is shown with that package's name and version.

from toporia.framework.parts.composition import ComposedMethod, explain
from toporia.framework.registry import install_hint, missing_dependencies


def registries():
    """Every plugin registry, by plugin kind."""
    from toporia.plugins.filters import FILTERS
    from toporia.plugins.interpolations import INTERPOLATIONS
    from toporia.plugins.methods import METHODS
    from toporia.plugins.models import MODELS
    from toporia.plugins.postprocessors import POSTPROCESSORS
    from toporia.plugins.representations import REPRESENTATIONS
    from toporia.plugins.responses import RESPONSES
    from toporia.plugins.schedules import SCHEDULES
    from toporia.plugins.updaters import UPDATERS
    return {"model": MODELS, "updater": UPDATERS, "representation": REPRESENTATIONS, "filter": FILTERS,
            "interpolation": INTERPOLATIONS, "response": RESPONSES, "schedule": SCHEDULES, "method": METHODS,
            "postprocessor": POSTPROCESSORS}


def _representation(found, solver):
    return found["representation"].get(solver.representation.get("type", "element_density"))


def representation_used(method_cls, solver):
    """The Representation class this method uses with this solver, or None when it keeps its own variables."""
    if not method_cls.capabilities.accepts_representation:
        return None
    return _representation(registries(), solver)


def solver_problems(method_cls, run):
    """Why this method cannot run with the parts the run's solver chooses — an empty list when it can.

    Capabilities.problems_with answers the same question for the scenario.  Here:
    an updater that moves one density per element (optimality criteria, BESO)
    cannot move the variables of any other design representation, and a
    schedule must drive a parameter its part can change during a run.
    """
    reasons = []
    representation = representation_used(method_cls, run.solver)
    if representation is not None and issubclass(method_cls, ComposedMethod):
        updater = method_cls.updater
        if updater.needs_element_densities and not representation.element_wise:
            from toporia.plugins.updaters import UPDATERS
            able = [cls.label for cls in UPDATERS.classes() if not cls.needs_element_densities]
            reasons.append(f"{updater.label} moves one density per element, so it cannot move the variables "
                           f"of {representation.label!r} (updaters that can: {', '.join(able)})")
    reasons += _variant_problems(method_cls, run)
    for spec in run.solver.schedules:
        path = spec.get("path", "")
        owner = scheduled_owner(method_cls, run, path)
        name = path.rpartition(".")[2]
        if owner is None:
            reasons.append(f"the schedule on {path!r} drives nothing: {method_cls.label} has no part there")
        elif name not in owner.schedulable:
            can = ", ".join(owner.schedulable) or "none of its parameters"
            reasons.append(f"{owner.label} cannot change {name!r} during a run (it can change: {can})")
    return reasons


def _variant_problems(method_cls, run):
    """Why solver.variants cannot be used as given (framework/parts/variants.py)."""
    from toporia.framework.parts.variants import COMBINE
    from toporia.framework.problem.run import apply_param
    spec = run.solver.variants
    if not spec:
        return []
    if not issubclass(method_cls, ComposedMethod):
        return [f"{method_cls.label} evaluates its own designs, so it cannot evaluate several variants; "
                f"variants need a method assembled from a model and an updater"]
    path, values = spec.get("path", ""), list(spec.get("values", ()))
    reasons = []
    name = path.rpartition(".")[2]
    if path == "m" or path.startswith(("schedules", "variants")):
        reasons.append(f"variants cannot vary {path!r}: every variant must share the mesh and the design variables")
    elif path.startswith("method.") and name in {p.name for p in method_cls.updater.params}:
        reasons.append(f"{path!r} belongs to the updater, which there is only one of; vary a part of the model")
    else:
        try:
            for value in values:
                apply_param(run, path, value)
        except (KeyError, IndexError, TypeError) as error:
            reasons.append(f"variants: {path!r} is not a parameter of this run ({error})")
    if len(values) < 2:
        reasons.append(f"variants need at least two values, got {values}")
    if spec.get("combine", "worst") not in COMBINE:
        reasons.append(f"variants combine as one of {sorted(COMBINE)}, not {spec.get('combine')!r}")
    nominal = spec.get("nominal")
    if nominal is not None and not 0 <= int(nominal) < len(values):
        reasons.append(f"the nominal variant {nominal} is not one of the {len(values)}")
    if any(schedule.get("path") == path for schedule in run.solver.schedules):
        reasons.append(f"{path!r} is both varied and scheduled; it can only be one")
    return reasons


def describe_variants(run):
    """The variants in words, e.g. "worst of filters[1].eta = 0.75, 0.5, 0.25 (...)"; "" when there are none."""
    from toporia.framework.parts.variants import COMBINE
    spec = run.solver.variants
    if not spec:
        return ""
    values = list(spec.get("values", ()))
    nominal = spec.get("nominal")
    nominal = len(values) // 2 if nominal is None else int(nominal)
    shown = f"{values[nominal]:g}" if 0 <= nominal < len(values) else "?"
    return (f"{COMBINE.get(spec.get('combine', 'worst'), '?').split(' (')[0].lower()} of "
            f"{spec.get('path')} = {', '.join(f'{v:g}' for v in values)}; {len(values)} solves per evaluation; "
            f"the design shown and its volume at {shown}")


def scheduled_owner(method_cls, run, path):
    """The class of the part whose parameter a schedule on `path` changes; None when there is none."""
    import re
    prefix, _, name = path.rpartition(".")
    capabilities = method_cls.capabilities
    found = registries()
    composed = issubclass(method_cls, ComposedMethod)
    if prefix == "method":
        if composed and name in {p.name for p in method_cls.updater.params}:
            return method_cls.updater
        return method_cls.model if composed else method_cls
    if not composed:
        return None
    if prefix == "interpolation" and capabilities.accepts_interpolation:
        return found["interpolation"].get(run.solver.interpolation.get("type", "simp"))
    if prefix == "representation" and capabilities.accepts_representation:
        return _representation(found, run.solver)
    if prefix == "objective":
        return found["response"].get(run.scenario.objective.get("type", "compliance"))
    indexed = re.fullmatch(r"(filters|constraints)\[(\d+)\]", prefix)
    if indexed:
        index = int(indexed[2])
        if indexed[1] == "filters" and capabilities.accepts_filters and index < len(run.solver.filter_specs):
            return found["filter"].get(run.solver.filter_specs[index].get("type", "density"))
        if indexed[1] == "constraints" and index < len(run.scenario.constraints):
            return found["response"].get(run.scenario.constraints[index]["type"])
    return None


def make_schedules(run):
    """The run's schedules as [(path, Schedule)], their parameters validated."""
    from toporia.framework.params import resolve_params
    found = registries()["schedule"]
    schedules = []
    for spec in run.solver.schedules:
        spec = dict(spec)
        path = spec.pop("path")
        cls = found.get(spec.pop("type", "steps"))
        schedules.append((path, cls(**resolve_params(f"schedule {cls.name!r} on {path!r}", cls.params, spec))))
    return schedules


def pipeline_parts(run):
    """Every plugin the run uses, as [(kind, class)], each once, in pipeline order.

    The model and the updater (or the whole method), the design representation,
    the material law and the filters when the method uses them, the objective
    and each constraint, the schedules, then the post-processors.
    """
    from toporia.plugins.methods import method_class
    found = registries()
    method_cls = method_class(run.solver.method)
    if issubclass(method_cls, ComposedMethod):
        parts = [("model", method_cls.model), ("updater", method_cls.updater)]
    else:
        parts = [("method", method_cls)]
    if method_cls.capabilities.accepts_representation:
        parts.append(("representation", _representation(found, run.solver)))
    if method_cls.capabilities.accepts_interpolation:
        parts.append(("interpolation", found["interpolation"].get(run.solver.interpolation.get("type", "simp"))))
    if method_cls.capabilities.accepts_filters:
        parts += [("filter", found["filter"].get(spec.get("type", "density"))) for spec in run.solver.filter_specs]
    parts.append(("response", found["response"].get(run.scenario.objective.get("type", "compliance"))))
    parts += [("response", found["response"].get(spec["type"])) for spec in run.scenario.constraints]
    parts += [("schedule", found["schedule"].get(spec.get("type", "steps"))) for spec in run.solver.schedules]
    parts += [("postprocessor", found["postprocessor"].get(spec["type"])) for spec in run.output.postprocess]
    unique = {}
    for kind, cls in parts:
        unique.setdefault((kind, cls.name), (kind, cls))
    return list(unique.values())


def part_origin(kind, cls):
    """Where a plugin came from: {"source": package or "toporia", "version": its version or None}."""
    from importlib import metadata

    import toporia
    from toporia.framework.registry import BUILT_IN
    registry = registries()[kind]
    source = registry.source(cls.name) if cls.name in registry else f"not registered ({cls.__module__})"
    if source == BUILT_IN:
        return {"source": BUILT_IN, "version": toporia.__version__}
    try:
        version = metadata.version(source)
    except (metadata.PackageNotFoundError, ValueError):
        version = None
    return {"source": source, "version": version}


def _labelled(kind, cls):
    """A plugin's label, with its package when it does not come from Toporia itself."""
    from toporia.framework.registry import BUILT_IN
    origin = part_origin(kind, cls)
    if origin["source"] == BUILT_IN:
        return cls.label
    version = f" {origin['version']}" if origin["version"] else ""
    return f"{cls.label} (from {origin['source']}{version})"


def pipeline_stages(run):
    """Return [(stage, description), ...] in the order the design flows through them."""
    from toporia.plugins.methods import method_class

    method_cls = method_class(run.solver.method)
    capabilities = method_cls.capabilities
    parts = pipeline_parts(run)
    responses = [_labelled(kind, cls) for kind, cls in parts if kind == "response"]
    filters_used = [_labelled(kind, cls) for kind, cls in parts if kind == "filter"]
    # The objective comes first among the responses; the volume budget is not a plugin.
    # Names only: the numbers live in their own panels, and this stays true while they are edited.
    objective, limits = responses[0], ["volume budget"] + responses[1:]

    schedules = _describe_schedules(run)
    post = [_labelled(kind, cls) for kind, cls in parts if kind == "postprocessor"]
    schedules += [("Post-processing", " -> ".join(post))] if post else []
    if not issubclass(method_cls, ComposedMethod):
        return [("Method", _labelled("method", method_cls)), ("Objective", objective),
                ("Constraints", ", ".join(limits))] + schedules

    if not capabilities.accepts_filters:
        filters = "inside the model"
    elif filters_used:
        # One label per filter in the chain, in order, even when a type repeats.
        filters = " -> ".join(_labelled("filter", registries()["filter"].get(spec.get("type", "density")))
                              for spec in run.solver.filter_specs)
    else:
        filters = "none"
    representation = next((cls for kind, cls in parts if kind == "representation"), None)
    design = (f"{capabilities.variable_kind} per element" if representation is None
              else _labelled("representation", representation)
              + ("" if representation.element_wise else ", projected onto the elements"))
    stages = [
        ("Design", design),
        ("Filters", filters),
        ("Physics", _labelled("model", method_cls.model)),
        ("Material", next((_labelled(kind, cls) for kind, cls in parts if kind == "interpolation"),
                          "inside the model")),
        ("Objective", objective),
        ("Constraints", ", ".join(limits)),
    ]
    updater = method_cls.updater
    if updater.flat_view:
        scale = updater.flat_objective_scale
        stages.append(("Optimiser sees", (
            "one vector of the free variables (fixed elements left out); "
            "f(x) and g(x) <= 0 with the volume budget first"
            + (f"; objective scaled to start at {scale:g}" if scale is not None else ""))))
        if updater.own_loop:
            handed_over = {"iteration": "each of its iterations", "evaluation": "each evaluation",
                           "final": "only its final design"}[updater.reports]
            stages[-1] = (stages[-1][0], stages[-1][1] + "; runs its own loop in the background "
                          f"and hands Toporia {handed_over}")
    else:
        stages.append(("Optimiser sees", "the design field itself"))
    stages.append(("Updater", _labelled("updater", updater)))
    variants = describe_variants(run)
    if variants:
        stages.insert(stages.index(("Constraints", ", ".join(limits))) + 1, ("Variants", variants))
    return stages + schedules


def _describe_schedules(run):
    """[("Schedules", "interpolation.penal 1 -> 3, +0.5 every 20 iterations; ...")], or [] when there are none."""
    try:
        described = [f"{path} {schedule.describe()}" for path, schedule in make_schedules(run)]
    except (KeyError, ValueError, TypeError) as error:
        described = [f"cannot be read: {error}"]
    return [("Schedules", "; ".join(described))] if described else []


def describe_pipeline(run):
    """The pipeline as one line, for the console."""
    return "  ->  ".join(f"{stage}: {text}" for stage, text in pipeline_stages(run))


def pipeline_notes(method, run=None):
    """Why the selected parts offer less than one of them could (see framework.parts.composition.explain).

    With the run, also why its choice of parts would be refused (solver_problems).
    """
    from toporia.plugins.methods import method_class

    method_cls = method_class(method)
    missing = missing_dependencies(method_cls)
    unavailable = ([f"Not installed here: {', '.join(missing)}. A run would stop at once; "
                    f"install it with: {install_hint(missing)}"] if missing else [])
    if run is not None:
        unavailable += [f"A run would be refused: {reason}." for reason in solver_problems(method_cls, run)]
        representation = representation_used(method_cls, run.solver)
        if representation is not None and representation.advice:
            unavailable.append(f"{representation.label}: {representation.advice}")
    if issubclass(method_cls, ComposedMethod):
        notes = unavailable + explain(method_cls.model, method_cls.updater)
        if method_cls.model.capabilities.constraints and not method_cls.capabilities.constraints:
            from toporia.plugins.updaters import UPDATERS
            able = [cls.label for cls in UPDATERS.classes() if cls.max_constraints != 0]
            if able:
                notes.append(f"Updaters that enforce constraints: {', '.join(able)}.")
        return notes
    capabilities = method_cls.capabilities
    notes = unavailable + [f"{method_cls.label} is a whole method: it evolves its own design representation "
             f"({capabilities.variable_kind.replace('_', ' ')}) with its own update rule."]
    if not capabilities.accepts_filters:
        notes.append("It does not use the Filters list.")
    if capabilities.max_constraints == 0:
        notes.append("It enforces only the volume budget.")
    return notes
