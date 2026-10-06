"""engine — the optimisation loop and the analysis modes built on it.

The engine drives a method through framework.parts.method.OptimizationMethod
and decides what to do with the density field that comes back: record it,
sweep a parameter across many runs, compare two designs, or measure a
sensitivity.  It knows nothing about SIMP, level sets, filters or finite
elements.

    loop.py      the one optimisation loop every mode goes through
    pipeline.py  names the parts a run is made of
    results.py, provenance.py, feasibility.py   what a run records
    modes/       one module per analysis mode
"""

from .loop import run_single
from .modes.compare_load_cases import compare_load_cases
from .modes.compare_two import compare_two
from .modes.sensitivity import sensitivity_field
from .modes.sensitivity_sweep import sensitivity_sweep, sensitivity_sweep_2d
from .modes.single import run_one
from .modes.sweep import sweep
from .modes.sweep_2d import sweep_2d
from .results import ResultStore

__all__ = [
    "run_single", "ResultStore", "run_one", "sweep", "sweep_2d", "compare_two",
    "compare_load_cases", "sensitivity_field", "sensitivity_sweep", "sensitivity_sweep_2d",
]
