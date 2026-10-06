"""engine — the optimisation loop and the analysis modes built on it.

The engine drives a method through framework.parts.method.OptimizationMethod
and decides what to do with the density field that comes back: record it,
sweep a parameter across many runs, compare two designs, or measure a
sensitivity.  It knows nothing about SIMP, level sets, filters or finite
elements.

    loop.py      the one optimisation loop every mode goes through
    records.py   what a run leaves behind: history, images, limit check, run.json
    pipeline.py  names the parts a run is made of, for the console and the GUI
    modes/       one module per analysis mode: single, sweep, compare, methods, sensitivity, check
"""

from .loop import run_single
from .modes.compare import compare_load_cases, compare_two
from .modes.methods import benchmark, compare_methods
from .modes.sensitivity import sensitivity_field, sensitivity_sweep, sensitivity_sweep_2d
from .modes.single import run_one
from .modes.sweep import sweep, sweep_2d
from .records import ResultStore

__all__ = [
    "run_single", "ResultStore", "run_one", "sweep", "sweep_2d", "compare_two",
    "compare_load_cases", "compare_methods", "benchmark", "sensitivity_field", "sensitivity_sweep",
    "sensitivity_sweep_2d",
]
