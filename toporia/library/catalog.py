"""library.catalog — every value the platform can vary, as parameter paths.

A *parameter path* addresses one value in a Run:

    volfrac                 a Scenario, Solver or Output field
    method.penal            a parameter of the selected method
    filters[1].beta         a parameter of the second filter in the pipeline
    load_cases[0].Fmag      a field of the first load case

core.run.apply_param writes to a path.  This module lists which paths exist
for a given setup, with human-readable labels — it is what the GUI's sweep,
comparison and sensitivity dropdowns show.  Only numeric parameters are listed,
because only numbers can be swept.
"""

from toporia.core import SCENARIO_PARAMS, SOLVER_PARAMS

from .filters import FILTERS
from .methods import METHODS

# The LoadCase fields a sweep may vary, with their display labels.
LOAD_CASE_FIELDS = (("Fmag", "Fmag"), ("Fa", "Angle"), ("weight", "Weight"))


def parameter_paths(method, filter_specs=(), n_load_cases=0):
    """Return [(label, path), ...] for every numeric value of this setup.

    Filter paths are included only when the method accepts filters, so the list
    never offers a parameter the run would ignore.
    """
    items = [(p.label, p.name) for p in SCENARIO_PARAMS + SOLVER_PARAMS if p.is_numeric]

    method_cls = METHODS.get(method)
    items += [(f"Method · {p.label}", f"method.{p.name}") for p in method_cls.params if p.is_numeric]

    if method_cls.capabilities.accepts_filters:
        for i, spec in enumerate(filter_specs):
            filter_cls = FILTERS.get(spec.get("type", "density"))
            items += [(f"Filter {i + 1} ({filter_cls.label}) · {p.label}", f"filters[{i}].{p.name}")
                      for p in filter_cls.params if p.is_numeric]

    for i in range(n_load_cases):
        items += [(f"LC {i + 1} · {label}", f"load_cases[{i}].{field}") for field, label in LOAD_CASE_FIELDS]
    return items
