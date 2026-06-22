# methods/__init__.py — algorithm factory
#
# This file is the public entry point for the methods package.
# All other code calls make_method("density") or make_method("levelset")
# and never imports the algorithm classes directly.
# This pattern (called a Factory) means you can add new algorithms later
# without changing any of the calling code — just add an entry to the dict.

from .density_top88 import DensityTop88Method
from .density_mma   import DensityMMAMethod
from .levelset_rbf  import LevelSetRBFMethod


def make_method(name: str):
    """Return a new instance of the requested optimisation algorithm.

    name: "density"  → SIMP density method (recommended for most cases)
          "levelset" → RBF level-set method (cleaner boundaries, slower)

    Raises ValueError for unrecognised names so the error message is clear.
    """
    methods = {
        "density":     DensityTop88Method,
        "density_mma": DensityMMAMethod,
        "mma":         DensityMMAMethod,
        "levelset":    LevelSetRBFMethod,
    }
    try:
        return methods[name.lower()]()   # .lower() makes matching case-insensitive
    except KeyError as exc:
        raise ValueError(f"Unknown optimization method: {name!r}."
                         f"  Choose from: {list(methods)}") from exc
