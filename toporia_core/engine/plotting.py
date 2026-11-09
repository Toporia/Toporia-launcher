# toporia_core/engine/plotting.py — matplotlib only when it is there.
#
# The core runs, records and is tested without matplotlib: the density images are written
# with toporia_core/engine/png.py, and the figures matplotlib draws (the history plot, the comparison,
# sweep and sensitivity figures) are made only when it is installed.  Without it they are
# skipped, with one notice per run of the program, and every number, CSV and run.json is
# written as before.

import functools
import importlib.util


def available():
    """True when matplotlib can be imported."""
    return importlib.util.find_spec("matplotlib") is not None


@functools.cache
def _say_once():
    print("  (figures skipped: pip install matplotlib to draw them; every number is still saved)")


def pyplot():
    """matplotlib.pyplot on the non-interactive Agg backend, or None (with one notice) when missing."""
    if not available():
        _say_once()
        return None
    import matplotlib
    if matplotlib.get_backend().lower() not in ("agg", "qtagg", "qt5agg", "module://matplotlib_inline.backend_inline"):
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt
