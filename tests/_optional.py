"""Skip a test whose method or plugin needs an optional package that is not installed here.

pyMOTO, NLopt, mmapy and the null-space optimiser are optional extras: a fresh install
without them must give a green suite, with those tests skipped rather than failed.
"""

import pytest


def missing_for(item):
    """The optional packages `item` (a Run, a method name, a plugin id or class) needs and lacks."""
    from toporia_core.framework.registry import missing_dependencies
    from toporia_library.methods import method_class
    if hasattr(item, "solver"):
        item = item.solver.method
    if isinstance(item, str) and ":" in item:            # a plugin id, e.g. "updater:pymoto_mma"
        from toporia_library.compatibility import part_class
        item = part_class(item)
        if item is None:                                   # a physics engine: declares nothing optional
            return []
    elif isinstance(item, str):
        item = method_class(item)
    return missing_dependencies(item)


def skip_without(item):
    """pytest.skip when `item` needs an optional package that is not installed."""
    missing = missing_for(item)
    if missing:
        pytest.skip(f"optional dependency: pip install {' '.join(missing)}")
