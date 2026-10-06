"""library.updaters — how a design moves.

An updater turns a model's Evaluation (objective, volume, gradients) into the
next design (see core.composition.Updater).  It knows nothing about the physics
that produced the numbers, so every updater works with every model.

Every Updater subclass in this package with a non-empty `name` is found by the
UPDATERS registry.  Modules starting with an underscore are not scanned.

    oc.py                 optimality criteria (top88)
    mma.py                method of moving asymptotes, one volume constraint
    simpl.py              entropic mirror descent on a latent variable (SiMPL)
    beso.py               bi-directional evolutionary ranking, binary designs
    pymoto_optimizers.py  pyMOTO's MMA and globally convergent GCMMA (optional)

Each works differently enough to be worth comparing: OC and MMA move densities
continuously inside the box, SiMPL moves them in logit space so the bounds hold
by construction, and BESO does not move them at all — it re-ranks and flips
elements between solid and void.
"""

from toporia.framework.parts.composition import Updater
from toporia.framework.registry import Registry

UPDATERS = Registry("updater", Updater, __name__)

__all__ = ["UPDATERS"]
