"""plugins.updaters — how a design moves.

An updater turns a model's Evaluation (objective, volume, gradients) into the
next design (see framework.parts.updater.Updater).  It knows nothing about the physics
that produced the numbers, so every updater works with every model.

Every Updater subclass in this package with a non-empty `name` is found by the
UPDATERS registry.  Modules starting with an underscore are not scanned.

    oc.py                 optimality criteria (top88)
    floating_projection.py damped OC with a mass-preserving floating threshold
                           and internal sharpness continuation (Huang 2020, 2021)
    mma.py                method of moving asymptotes, one volume constraint
    conlin.py             CONLIN, convex linearisation (MMA without moving asymptotes), any number of constraints
    oc_multi.py           optimality criteria with a multiplier per constraint
    simpl.py              entropic mirror descent on a latent variable (SiMPL)
    beso.py               bi-directional evolutionary ranking, binary designs
    beso_hard.py          hard-kill BESO: removed elements at exactly the void bound
    adam.py               Adam with the volume budget as an augmented Lagrangian
    pto.py                proportional topology optimisation (baseline)
    pymoto_optimizers.py pyMOTO's MMA and globally convergent GCMMA (optional)
    mmapy_optimizers.py   Svanberg's MMA and GCMMA via mmapy (optional, GPL-3)
    nullspace.py          Feppon's null-space optimiser (optional, GPL-3, runs its own loop)

Each works differently enough to be worth comparing: OC and MMA move densities
continuously inside the box, SiMPL moves them in logit space so the bounds hold
by construction, and BESO does not move them at all — it re-ranks and flips
elements between solid and void.
"""

from toporia.framework.parts.updater import Updater
from toporia.framework.registry import Registry

UPDATERS = Registry("updater", Updater, __name__)

__all__ = ["UPDATERS"]
