"""engine — the optimisation loop and the analysis modes built on it.

The engine drives a method through core.contract.OptimizationMethod and decides
what to do with the density field that comes back: record it, sweep a parameter
across many runs, compare two designs, or measure a sensitivity.

It knows nothing about SIMP, level sets, filters or finite elements.  Every name
below is one selectable mode in the GUI's Mode dropdown.
"""

from .compare_load_cases import compare_load_cases
from .compare_two import compare_two
from .results import ResultStore
from .run_one import run_one
from .runner import run_single
from .sensitivity import sensitivity_field
from .sensitivity_sweep import sensitivity_sweep, sensitivity_sweep_2d
from .sweep import sweep
from .sweep_2d import sweep_2d

__all__ = [
    "run_single",
    "ResultStore",
    "run_one",
    "sweep",
    "sweep_2d",
    "compare_two",
    "compare_load_cases",
    "sensitivity_field",
    "sensitivity_sweep",
    "sensitivity_sweep_2d",
]
