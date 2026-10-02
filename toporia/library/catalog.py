"""library.catalog — every value the platform can vary, as parameter paths.

A *parameter path* addresses one value in a Run:

    volfrac                 a Scenario, Solver or Output field
    method.penal            a parameter of the selected method
    filters[1].beta         a parameter of the second filter in the pipeline
    objective.<param>       a parameter of the scenario's objective
    constraints[0].limit    a parameter of the first scenario constraint
    load_cases[0].Fmag      a field of the first load case

core.run.apply_param writes to a path.  This module lists which paths exist
for a given setup, with human-readable labels — it is what the GUI's sweep,
comparison and sensitivity dropdowns show.  Only numeric parameters are listed,
because only numbers can be swept.
"""

from toporia.core import SCENARIO_PARAMS, SOLVER_PARAMS

from .filters import FILTERS
from .methods import method_class
from .responses import RESPONSES

# The LoadCase fields a sweep may vary, with their display labels.
LOAD_CASE_FIELDS = (("Fmag", "Fmag"), ("Fa", "Angle"), ("weight", "Weight"))


def _numeric(label_prefix, path_prefix, params):
    return [(f"{label_prefix} · {p.label}", f"{path_prefix}{p.name}") for p in params if p.is_numeric]


def parameter_paths(method, filter_specs=(), n_load_cases=0, objective=None, constraints=()):
    """Return [(label, path), ...] for every numeric value of this setup.

    Filter and constraint paths are included only when the method can use
    them, so the list never offers a parameter the run would ignore or refuse.
    """
    items = [(p.label, p.name) for p in SCENARIO_PARAMS + SOLVER_PARAMS if p.is_numeric]

    method_cls = method_class(method)
    capabilities = method_cls.capabilities
    items += _numeric("Method", "method.", method_cls.params)

    if capabilities.accepts_filters:
        for i, spec in enumerate(filter_specs):
            filter_cls = FILTERS.get(spec.get("type", "density"))
            items += _numeric(f"Filter {i + 1} ({filter_cls.label})", f"filters[{i}].", filter_cls.params)

    if objective:
        objective_cls = RESPONSES.get(objective.get("type", "compliance"))
        items += _numeric("Objective", "objective.", objective_cls.params)

    if capabilities.constraints and capabilities.max_constraints != 0:
        for i, spec in enumerate(constraints):
            constraint_cls = RESPONSES.get(spec["type"])
            items += _numeric(f"Constraint {i + 1} ({constraint_cls.label})", f"constraints[{i}].",
                              constraint_cls.params)

    for i in range(n_load_cases):
        items += [(f"LC {i + 1} · {label}", f"load_cases[{i}].{field}") for field, label in LOAD_CASE_FIELDS]
    return items
