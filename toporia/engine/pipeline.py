# engine/pipeline.py — what a run is made of, in words.
#
# A run's method is assembled from parts: the design passes through the
# filters, the physics engine solves it, the responses are measured, and the
# updater moves the design.  This module names each part for a given Run, so
# the console and the GUI show exactly the same chain:
#
#     design -> filters -> physics (material law) -> objective, constraints -> updater -> design
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
    from toporia.plugins.responses import RESPONSES
    from toporia.plugins.updaters import UPDATERS
    return {"model": MODELS, "updater": UPDATERS, "filter": FILTERS, "interpolation": INTERPOLATIONS,
            "response": RESPONSES, "method": METHODS}


def pipeline_parts(run):
    """Every plugin the run uses, as [(kind, class)], each once, in pipeline order.

    The model and the updater (or the whole method), the material law and the
    filters when the method uses them, then the objective and each constraint.
    """
    from toporia.plugins.methods import method_class
    found = registries()
    method_cls = method_class(run.solver.method)
    if issubclass(method_cls, ComposedMethod):
        parts = [("model", method_cls.model), ("updater", method_cls.updater)]
    else:
        parts = [("method", method_cls)]
    if method_cls.capabilities.accepts_interpolation:
        parts.append(("interpolation", found["interpolation"].get(run.solver.interpolation.get("type", "simp"))))
    if method_cls.capabilities.accepts_filters:
        parts += [("filter", found["filter"].get(spec.get("type", "density"))) for spec in run.solver.filter_specs]
    parts.append(("response", found["response"].get(run.scenario.objective.get("type", "compliance"))))
    parts += [("response", found["response"].get(spec["type"])) for spec in run.scenario.constraints]
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

    if not issubclass(method_cls, ComposedMethod):
        return [("Method", _labelled("method", method_cls)), ("Objective", objective),
                ("Constraints", ", ".join(limits))]

    if not capabilities.accepts_filters:
        filters = "inside the model"
    elif filters_used:
        # One label per filter in the chain, in order, even when a type repeats.
        filters = " -> ".join(_labelled("filter", registries()["filter"].get(spec.get("type", "density")))
                              for spec in run.solver.filter_specs)
    else:
        filters = "none"
    stages = [
        ("Design", f"{capabilities.variable_kind} per element"),
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
    return stages


def describe_pipeline(run):
    """The pipeline as one line, for the console."""
    return "  ->  ".join(f"{stage}: {text}" for stage, text in pipeline_stages(run))


def pipeline_notes(method):
    """Why the selected parts offer less than one of them could (see framework.parts.composition.explain)."""
    from toporia.plugins.methods import method_class

    method_cls = method_class(method)
    missing = missing_dependencies(method_cls)
    unavailable = ([f"Not installed here: {', '.join(missing)}. A run would stop at once; "
                    f"install it with: {install_hint(missing)}"] if missing else [])
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
