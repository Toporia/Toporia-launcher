"""plugins.problems — benchmark and application problems, one per module.

Each module in this package defines:

    NAME        display name, shown in the GUI and accepted by the CLI
    ORDER       menu position (lower first)
    ABOUT       one sentence on what the problem is (optional)
    REFERENCE   where it comes from (optional); both are shown in the GUI's help
    scenario()  -> Scenario   what is being solved
    solver()    -> Solver     recommended settings (optional; defaults otherwise)

    LISTED      False for a problem only the checks and tests use (optional)

Modules are found automatically: adding a file adds a preset.  Modules whose
name starts with an underscore are skipped.

`toporia export PRESET DIR` writes any preset as editable JSON files.
"""

# The lookup lives in the core (toporia_core/framework/problem/presets.py), which finds these
# modules through the "toporia.problems" entry point; the research help stays here.
from toporia_core.framework.problem.presets import (
    DEFAULT_PROBLEM,
    get_default_run,
    get_run,
    problem_info,
    problem_names,
)
from toporia_core.framework.problem.presets import preset_modules as _modules


def problem_description(name):
    """Optional structured research explanation, without importing GUI or plotting code.

    ABOUT/REFERENCE and problem_info remain the short, backwards-compatible API.
    Figure presets declare DESCRIPTION alongside the runnable setup; known
    original presets obtain mathematical explanations without changing recipes.
    """
    module = _modules()[name]
    if hasattr(module, "DESCRIPTION"):
        return module.DESCRIPTION
    if hasattr(module, "_description"):          # built when asked, e.g. from the solver settings
        return module._description()
    from ._research_defaults import original_description
    return original_description(module)


__all__ = ["DEFAULT_PROBLEM", "get_default_run", "get_run", "problem_info", "problem_names", "problem_description"]
