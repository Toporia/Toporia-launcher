"""plugins.methods — the selectable optimisation methods.

A method is named in solver.method in one of two ways:

    "<model>+<updater>"   any model (toporia_library/models) with any updater
                          (toporia_library/updaters), e.g. "q4+oc" or "pymoto_elastic+pymoto_gcmma".
                          The pairing is built on demand; nothing is declared per pair.
    "<method>"            a whole method that implements framework.parts.method.OptimizationMethod
                          itself, because it does not split into a model and an updater —
                          the RBF level set evolves its own representation with its own
                          volume control.

Every OptimizationMethod subclass in this package with a non-empty `name` is
found by the METHODS registry; there is no list to maintain.  Modules starting
with an underscore hold shared helpers and are not scanned.

Names used before the split into parts ("density", "density_mma", "beso", ...)
are still accepted; PRESETS says what each one stands for.
"""

# The registry and the name lookups live in the core (toporia_core/framework/registries.py);
# this package is the registry's built-in source, declared in pyproject.toml.
from toporia_core.framework.registries import (
    METHODS,
    PRESETS,
    canonical_name,
    make_method,
    method_class,
    method_classes,
)

__all__ = ["METHODS", "PRESETS", "method_class", "method_classes", "canonical_name", "make_method"]
