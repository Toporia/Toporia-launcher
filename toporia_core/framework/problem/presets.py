# framework/problem/presets.py — ready-made problems, found by name.
#
# A preset is a module with
#
#     NAME        display name, shown in the GUI and accepted by the command line
#     ORDER       menu position (lower first, optional)
#     ABOUT       one sentence on what the problem is (optional)
#     REFERENCE   where it comes from (optional)
#     LISTED      False for a problem only the checks and tests use (optional)
#     scenario()  -> Scenario   what is being solved
#     solver()    -> Solver     recommended settings (optional; defaults otherwise)
#     output()    -> Output     its post-processing (optional), e.g. a clean solid at the end
#
# Presets come from the entry-point group "toporia.problems", a package (every module
# in it not starting with an underscore) or a single module.  Toporia's own presets,
# toporia_library/problems/, are declared there in pyproject.toml, so the core finds
# them without importing the library by name.

import importlib
import importlib.metadata
import pkgutil
from dataclasses import replace
from functools import lru_cache

from .run import Run
from .solver import Solver

GROUP = "toporia.problems"
DEFAULT_PROBLEM = "MBB Beam"


def _presets_in(module):
    if hasattr(module, "NAME") and hasattr(module, "scenario"):
        yield module
    for info in pkgutil.iter_modules(getattr(module, "__path__", [])):
        if not info.name.startswith("_"):
            yield from _presets_in(importlib.import_module(f"{module.__name__}.{info.name}"))


@lru_cache(maxsize=1)
def preset_modules():
    """{display name: module} of every preset, listed or not."""
    found = {}
    for entry_point in importlib.metadata.entry_points(group=GROUP):
        for module in _presets_in(entry_point.load()):
            if module.NAME in found and found[module.NAME] is not module:
                raise RuntimeError(f"Two problems are named {module.NAME!r}")
            found[module.NAME] = module
    return found


def problem_names():
    """Display names of every listed problem, in menu order.

    A module with LISTED = False (a test problem) is left out here, so the GUI, the command
    line and the catalogue never offer it, but get_run() still finds it by name.
    """
    modules = {name: module for name, module in preset_modules().items() if getattr(module, "LISTED", True)}
    return sorted(modules, key=lambda name: (getattr(modules[name], "ORDER", 100), name))


def get_run(name):
    """Return the named problem as a Run: its scenario plus its recommended solver."""
    try:
        module = preset_modules()[name]
    except KeyError:
        raise KeyError(f"Unknown problem {name!r}. Available: {problem_names()}") from None
    solver = module.solver() if hasattr(module, "solver") else Solver()
    run = Run(scenario=module.scenario(), solver=solver)
    if hasattr(module, "output"):          # e.g. a truss preset that makes a clean solid at the end
        run = replace(run, output=module.output())
    return run


def problem_info(name):
    """What the named problem is and where it comes from, as (about, reference); empty when not stated."""
    module = preset_modules()[name]
    return getattr(module, "ABOUT", ""), getattr(module, "REFERENCE", "")


def get_default_run():
    """Return the default startup problem (the MBB beam) as a Run."""
    return get_run(DEFAULT_PROBLEM)
