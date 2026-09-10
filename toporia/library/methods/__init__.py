"""library.methods — optimisation algorithms and their filters.

Every OptimizationMethod subclass in this package with a non-empty `name` is
found automatically by the METHODS registry; there is no list to maintain.  To
add an algorithm, add a module here that declares name, label, params and
capabilities (see core/contract.py).

Modules starting with an underscore hold shared helpers and are not scanned.
"""

from toporia.core.contract import OptimizationMethod
from toporia.core.registry import Registry

METHODS = Registry("method", OptimizationMethod, __name__)


def make_method(name: str):
    """Return a new instance of the named algorithm.

    Names are case-insensitive and aliases are accepted ("mma" -> "density_mma").
    Raises ValueError listing the available names for an unknown one.
    """
    return METHODS.get(name)()


__all__ = ["METHODS", "make_method"]
