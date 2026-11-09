# toporia_core/engine/modes/choices.py — a choice of part as a sweep variable.
#
# A sweep varies a numeric parameter path ("volfrac", "filters[0].rmin") over a range.  A
# choice path varies which part a run uses, over a few named options: a discrete variable,
# where Compare Methods' grid meets the sweep.
#
#     choice:updater          the updater of a model + updater method   (oc, mma, conlin, ...)
#     choice:model            the physics model of a model + updater    (q4, q4_dynamic, ...)
#     choice:method           the whole method                          (q4+oc, levelset, truss, ...)
#     choice:interpolation    the material law                          (simp, ramp, ...)
#     choice:representation   what the design variables are            (element_density, mmc, ...)
#     choice:filters[i]       the type of filter i                      (density, sensitivity, pde, ...)
#
# A new part gets its own default parameters; everything else of the run stays as it is.  A
# combination that cannot run (an updater that cannot minimise the objective, a model without
# the representation's support, a missing optional package) is not run: its cell says why.

import re

from toporia_core.framework.problem.run import apply_param

PREFIX = "choice:"
KINDS = ("updater", "model", "method", "interpolation", "representation")


def is_choice(path):
    """True for a choice path such as "choice:updater"."""
    return isinstance(path, str) and path.startswith(PREFIX)


def choice_label(path):
    """The part a choice path varies, in words: "updater", "filter 1", ..."""
    kind = path[len(PREFIX):]
    found = re.fullmatch(r"filters\[(\d+)\]", kind)
    return f"filter {int(found[1]) + 1}" if found else kind


def apply_choice(run, path, value):
    """The run with the part named by `path` replaced by `value` (with its default parameters)."""
    from dataclasses import replace
    kind = path[len(PREFIX):]
    solver = run.solver
    if kind in ("updater", "model"):
        if "+" not in solver.method:
            raise ValueError(f"{solver.method!r} is a whole method: it has no {kind} to vary")
        model, updater = solver.method.split("+", 1)
        method = f"{model}+{value}" if kind == "updater" else f"{value}+{updater}"
        return replace(run, solver=replace(solver, method=method, method_params={}))
    if kind == "method":
        return replace(run, solver=replace(solver, method=str(value), method_params={}))
    if kind == "interpolation":
        return replace(run, solver=replace(solver, interpolation={"type": str(value)}))
    if kind == "representation":
        return replace(run, solver=replace(solver, representation={"type": str(value)}))
    found = re.fullmatch(r"filters\[(\d+)\]", kind)
    if found:
        index = int(found[1])
        specs = [dict(spec) for spec in solver.filter_specs]
        if index >= len(specs):
            raise ValueError(f"There is no filter {index + 1} to vary (the run has {len(specs)})")
        specs[index] = {"type": str(value)}
        return replace(run, solver=replace(solver, filter_specs=specs))
    raise ValueError(f"Unknown choice {path!r}; choices: " + ", ".join(PREFIX + k for k in KINDS)
                     + f", {PREFIX}filters[i]")


def assign(run, path, value):
    """Apply one sweep assignment: a numeric parameter path or a choice path."""
    return apply_choice(run, path, value) if is_choice(path) else apply_param(run, path, value)


def show(value):
    """A value as a cell title shows it: 3 significant digits for numbers, the name for a choice."""
    return f"{value:.3g}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


def problems(run):
    """Why a run cannot be made — an empty list when it can (unknown parts, capabilities, packages)."""
    from toporia_core.engine.pipeline import solver_problems
    from toporia_core.framework.registries import FILTERS, INTERPOLATIONS, REPRESENTATIONS, method_class
    from toporia_core.framework.registry import install_hint, missing_dependencies
    unknown = [f"no {kind} {name!r}" for kind, registry, name in (
        ("material law", INTERPOLATIONS, run.solver.interpolation.get("type", "simp")),
        ("representation", REPRESENTATIONS, run.solver.representation.get("type", "element_density")),
        *(("filter", FILTERS, spec.get("type")) for spec in run.solver.filter_specs)) if name not in registry.names()]
    if unknown:
        return unknown
    try:
        cls = method_class(run.solver.method)
    except (KeyError, ValueError) as error:
        return [str(error).strip("'\"")]
    reasons = list(cls.capabilities.problems_with(run.scenario)) + list(solver_problems(cls, run))
    missing = missing_dependencies(cls)
    if missing:
        reasons.append(f"not installed: {install_hint(missing)}")
    return reasons
