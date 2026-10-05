# engine/pipeline.py — what a run is made of, in words.
#
# A run's method is assembled from parts: the design passes through the
# filters, the physics engine solves it, the responses are measured, and the
# updater moves the design.  This module names each part for a given Run, so
# the console and the GUI show exactly the same chain:
#
#     design -> filters -> physics -> objective, constraints -> updater -> design
#
# Whole methods (the RBF level set) do not split into parts; for those the
# chain is the method itself.

from toporia.core.composition import ComposedMethod, explain


def pipeline_stages(run):
    """Return [(stage, description), ...] in the order the design flows through them."""
    from toporia.library.filters import FILTERS
    from toporia.library.methods import method_class
    from toporia.library.responses import RESPONSES

    method_cls = method_class(run.solver.method)
    capabilities = method_cls.capabilities
    scenario = run.scenario

    objective = RESPONSES.get(scenario.objective.get("type", "compliance")).label
    # Names only: the numbers live in their own panels, and this stays true while they are edited.
    limits = ["volume budget"] + [RESPONSES.get(spec["type"]).label for spec in scenario.constraints]

    if not issubclass(method_cls, ComposedMethod):
        return [("Method", method_cls.label), ("Objective", objective), ("Constraints", ", ".join(limits))]

    if not capabilities.accepts_filters:
        filters = "inside the model"
    elif run.solver.filter_specs:
        filters = " -> ".join(FILTERS.get(spec.get("type", "density")).label for spec in run.solver.filter_specs)
    else:
        filters = "none"
    stages = [
        ("Design", f"{capabilities.variable_kind} per element"),
        ("Filters", filters),
        ("Physics", method_cls.model.label),
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
    stages.append(("Updater", updater.label))
    return stages


def describe_pipeline(run):
    """The pipeline as one line, for the console."""
    return "  ->  ".join(f"{stage}: {text}" for stage, text in pipeline_stages(run))


def pipeline_notes(method):
    """Why the selected parts offer less than one of them could (see core.composition.explain)."""
    from toporia.library.methods import method_class

    method_cls = method_class(method)
    if issubclass(method_cls, ComposedMethod):
        notes = explain(method_cls.model, method_cls.updater)
        if method_cls.model.capabilities.constraints and not method_cls.capabilities.constraints:
            from toporia.library.updaters import UPDATERS
            able = [cls.label for cls in UPDATERS.classes() if cls.max_constraints != 0]
            if able:
                notes.append(f"Updaters that enforce constraints: {', '.join(able)}.")
        return notes
    capabilities = method_cls.capabilities
    notes = [f"{method_cls.label} is a whole method: it evolves its own design representation "
             f"({capabilities.variable_kind.replace('_', ' ')}) with its own update rule."]
    if not capabilities.accepts_filters:
        notes.append("It does not use the Filters list.")
    if capabilities.max_constraints == 0:
        notes.append("It enforces only the volume budget.")
    return notes
