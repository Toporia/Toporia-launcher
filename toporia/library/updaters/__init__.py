"""library.updaters — how a design moves.

An updater turns a model's Evaluation (objective, volume, gradients) into the
next design (see core.composition.Updater).  It knows nothing about the physics
that produced the numbers, so every updater works with every model.

Every Updater subclass in this package with a non-empty `name` is found by the
UPDATERS registry.  Modules starting with an underscore are not scanned.

    oc.py                 optimality criteria (top88)
    mma.py                method of moving asymptotes, one volume constraint
    pymoto_optimizers.py  pyMOTO's MMA and globally convergent GCMMA (optional)
"""

from toporia.core.composition import Updater
from toporia.core.registry import Registry

UPDATERS = Registry("updater", Updater, __name__)

__all__ = ["UPDATERS"]
