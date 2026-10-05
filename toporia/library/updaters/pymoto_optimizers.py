# library/updaters/pymoto_optimizers.py — pyMOTO's MMA and GCMMA as updaters.
#
# pyMOTO's optimisers expect a pyMOTO network.  To drive ANY Toporia model with
# them, the model's flat view (core/flat.py) is presented to pyMOTO as a
# single module:
#
#     pyMOTO Signal x ──[_FlatModule]──> f, g_volume, g_1, …     (FlatProblem.f, .g)
#                           │
#                           └─ sensitivities: FlatProblem.df, .dg
#
# so pyMOTO's MMA — or its globally convergent GCMMA, which re-evaluates the
# model at trial designs inside an iteration — can move a design whose physics
# it knows nothing about, under any number of constraints.
#
# The flat view does all the translation: only the free variables are handed
# over (pinned elements have equal bounds, and pyMOTO's MMA divides by the
# bound range), the volume budget is the first constraint, and the objective
# is scaled to start at 10, because MMA's subproblem assumes objective and
# constraints of similar magnitude — without it pyMOTO's subsolver stalled at
# its iteration cap every step (a volume objective near 100 beside constraints
# near 1 did exactly that).
#
# Requires the optional dependency:  pip install "toporia[pymoto]"

import numpy as np

from toporia.core.composition import Updater
from toporia.library.models.pymoto_elastic import import_pymoto

from ._common import MOVE

_module_class = None


def _flat_module(pym):
    """Build (once) the pyMOTO Module that wraps a FlatProblem.  Lazy: pyMOTO is optional."""
    global _module_class
    if _module_class is None:

        class _FlatModule(pym.Module):
            """A FlatProblem seen by pyMOTO: x -> (f, g_0, g_1, ...)."""

            def __init__(self, flat):
                self.flat = flat

            def __call__(self, x):
                # The flat view computes gradients along with the values, so the
                # sensitivity pass below needs no second solve.
                self.x = np.array(x, dtype=float)
                return (self.flat.f(self.x), *self.flat.g(self.x))

            def _sensitivity(self, *seeds):
                gradients = [self.flat.df(self.x), *self.flat.dg(self.x)]
                total = np.zeros_like(gradients[0])
                for seed, gradient in zip(seeds, gradients):
                    if seed is not None:
                        total = total + seed * gradient
                return total

        _module_class = _FlatModule
    return _module_class


class PymotoMMAUpdater(Updater):
    """pyMOTO's method of moving asymptotes (Svanberg 2007 variant)."""

    name = "pymoto_mma"
    label = "MMA (pyMOTO)"
    order = 30
    params = (MOVE,)
    max_constraints = None   # pyMOTO's MMA takes any number of constraints
    flat_view = True
    flat_objective_scale = 10.0
    version = "MMA2007"      # pyMOTO's mmaversion: "MMA1987", "MMA2007" or "GCMMA"

    def initialize(self, model, settings):
        pym = import_pymoto()
        flat = self.flat_problem(model)
        self.s_x = pym.Signal("x", flat.x0.copy(), min=flat.lower, max=flat.upper)
        with pym.Network() as network:
            outputs = _flat_module(pym)(flat)(self.s_x)
        self.optimizer = pym.MMA(
            self.s_x, list(outputs), network,
            move=settings["move"], xmin=flat.lower, xmax=flat.upper,
            verbosity=0, mmaversion=self.version,
        )

    def update(self, x, evaluation, completed):
        # The design has just been evaluated, so hand pyMOTO those numbers
        # rather than letting it evaluate the model a second time.
        flat = self.flat
        flat.remember(x, evaluation)
        x_free = flat.reduce(x)
        values = np.array([flat.f(x_free), *flat.g(x_free)])
        gradients = np.vstack([flat.df(x_free), flat.dg(x_free)])
        x_new, _, _ = self.optimizer.step(x=x_free, g=values, dg=gradients)
        return flat.expand(x_new)


class PymotoGCMMAUpdater(PymotoMMAUpdater):
    """pyMOTO's globally convergent MMA: re-evaluates trial designs until the step is safe."""

    name = "pymoto_gcmma"
    label = "GCMMA (pyMOTO)"
    order = 40
    version = "GCMMA"
