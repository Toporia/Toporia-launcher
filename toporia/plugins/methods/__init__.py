"""library.methods — the selectable optimisation methods.

A method is named in solver.method in one of two ways:

    "<model>+<updater>"   any model (library/models) with any updater
                          (library/updaters), e.g. "q4+oc" or "pymoto_elastic+pymoto_gcmma".
                          The pairing is built on demand; nothing is declared per pair.
    "<method>"            a whole method that implements core.contract.OptimizationMethod
                          itself, because it does not split into a model and an updater —
                          the RBF level set evolves its own representation with its own
                          volume control.

Every OptimizationMethod subclass in this package with a non-empty `name` is
found by the METHODS registry; there is no list to maintain.  Modules starting
with an underscore hold shared helpers and are not scanned.

Names used before the split into parts ("density", "density_mma", "beso", ...)
are still accepted; PRESETS says what each one stands for.
"""

from toporia.framework.parts.composition import SEPARATOR, compose
from toporia.framework.parts.method import OptimizationMethod
from toporia.framework.registry import Registry

METHODS = Registry("method", OptimizationMethod, __name__)

#: Method names from before methods were split into a model and an updater.
PRESETS = {
    "density": "q4+oc",
    "density_mma": "q4+mma",
    "mma": "q4+mma",
    "density_simpl": "q4+simpl",
    "beso": "q4+beso",
    "density_gcmma": "q4+pymoto_gcmma",
    "pymoto": "pymoto_elastic+pymoto_mma",
}


def canonical_name(name):
    """The explicit form of a method name: presets expanded, model and updater canonical."""
    return method_class(name).name


def method_class(name):
    """Return the method class for a name in either form (see the module docstring).

    Case-insensitive; registry aliases and PRESETS are accepted.  Raises
    ValueError naming what is available for an unknown name.
    """
    from toporia.plugins.models import MODELS
    from toporia.plugins.updaters import UPDATERS

    key = str(name).strip().lower()
    key = PRESETS.get(key, key)
    if SEPARATOR in key:
        model, _, updater = key.partition(SEPARATOR)
        return compose(MODELS.get(model.strip()), UPDATERS.get(updater.strip()))
    try:
        return METHODS.get(key)
    except ValueError:
        raise ValueError(
            f"Unknown method {name!r}. Use '<model>{SEPARATOR}<updater>' with a model from "
            f"{MODELS.names()} and an updater from {UPDATERS.names()}, or one of {METHODS.names()}."
        ) from None


def method_classes():
    """Every selectable method: each model with each updater, then the whole methods."""
    from toporia.plugins.models import MODELS
    from toporia.plugins.updaters import UPDATERS

    pairs = [compose(model, updater) for model in MODELS.classes() for updater in UPDATERS.classes()]
    return pairs + METHODS.classes()


def make_method(name: str):
    """Return a new instance of the named method (either form; see method_class)."""
    return method_class(name)()


__all__ = ["METHODS", "PRESETS", "method_class", "method_classes", "canonical_name", "make_method"]
