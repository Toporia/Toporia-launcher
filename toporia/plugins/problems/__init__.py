"""plugins.problems — benchmark and application problems, one per module.

Each module in this package defines:

    NAME        display name, shown in the GUI and accepted by the CLI
    ORDER       menu position (lower first)
    scenario()  -> Scenario   what is being solved
    solver()    -> Solver     recommended settings (optional; defaults otherwise)

Modules are found automatically: adding a file adds a preset.  Modules whose
name starts with an underscore are skipped.

`toporia export PRESET DIR` writes any preset as editable JSON files.
"""

import importlib
import pkgutil
from functools import lru_cache

from toporia.framework import Run, Solver

DEFAULT_PROBLEM = "MBB Beam"


@lru_cache(maxsize=1)
def _modules():
    found = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        if hasattr(module, "NAME") and hasattr(module, "scenario"):
            if module.NAME in found:
                raise RuntimeError(f"Two problems are named {module.NAME!r}")
            found[module.NAME] = module
    return found


def problem_names():
    """Display names of every problem, in menu order."""
    modules = _modules()
    return sorted(modules, key=lambda name: (getattr(modules[name], "ORDER", 100), name))


def get_run(name):
    """Return the named problem as a Run: its scenario plus its recommended solver."""
    try:
        module = _modules()[name]
    except KeyError:
        raise KeyError(f"Unknown problem {name!r}. Available: {problem_names()}") from None
    solver = module.solver() if hasattr(module, "solver") else Solver()
    return Run(scenario=module.scenario(), solver=solver)


def get_default_run():
    """Return the default startup problem (the MBB beam) as a Run."""
    return get_run(DEFAULT_PROBLEM)


__all__ = ["DEFAULT_PROBLEM", "get_default_run", "get_run", "problem_names"]
