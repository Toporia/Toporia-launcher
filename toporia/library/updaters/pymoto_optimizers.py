# library/updaters/pymoto_optimizers.py — pyMOTO's MMA and GCMMA as updaters.
#
# pyMOTO's optimisers expect a pyMOTO network.  To drive ANY Toporia model with
# them, the model is presented to pyMOTO as a single module:
#
#     pyMOTO Signal x_free ──[_ToporiaModel]──> objective, volume budget, constraint 1, …
#                               │
#                               └─ calls model.evaluate() and hands back its gradients
#
# so pyMOTO's MMA — or its globally convergent GCMMA, which re-evaluates the
# model at trial designs inside an iteration — can move a design whose physics
# it knows nothing about, under any number of constraints.
#
# Only the free variables are handed to pyMOTO.  Elements pinned by passive or
# void regions have equal lower and upper bounds, and pyMOTO's MMA divides by
# that range; leaving them out keeps it well defined and changes nothing,
# because a pinned variable cannot move anyway.
#
# Requires the optional dependency:  pip install "toporia[pymoto]"

import numpy as np

from toporia.core.composition import Updater
from toporia.library.models.pymoto_elastic import import_pymoto

from ._common import MOVE

_module_class = None


def _model_module(pym):
    """Build (once) the pyMOTO Module that wraps a Toporia model.  Lazy: pyMOTO is optional."""
    global _module_class
    if _module_class is None:

        class _ToporiaModel(pym.Module):
            """A Toporia model seen by pyMOTO: free design -> (objective, constraints...)."""

            def __init__(self, updater):
                self.updater = updater

            def __call__(self, x_free):
                return self.updater._evaluate_free(x_free)

            def _sensitivity(self, *seeds):
                gradients = self.updater._gradients
                total = np.zeros_like(gradients[0])
                for seed, gradient in zip(seeds, gradients):
                    if seed is not None:
                        total = total + seed * gradient
                return total

        _module_class = _ToporiaModel
    return _module_class


class PymotoMMAUpdater(Updater):
    """pyMOTO's method of moving asymptotes (Svanberg 2007 variant)."""

    name = "pymoto_mma"
    label = "MMA (pyMOTO)"
    order = 30
    params = (MOVE,)
    max_constraints = None   # pyMOTO's MMA takes any number of constraints
    version = "MMA2007"      # pyMOTO's mmaversion: "MMA1987", "MMA2007" or "GCMMA"

    def initialize(self, model, settings):
        pym = import_pymoto()
        self.model = model
        lower, upper = model.bounds()
        self.shape = lower.shape
        lower, upper = lower.reshape(-1, order="F"), upper.reshape(-1, order="F")
        self.free = upper > lower
        self.pinned = lower.copy()   # a pinned element sits at its (equal) bounds
        self._objective_scale = None   # fixed from the first evaluation; see _responses

        start = model.initial_design().reshape(-1, order="F")[self.free]
        self.s_x = pym.Signal("x", start.copy(), min=lower[self.free], max=upper[self.free])
        with pym.Network() as network:
            outputs = _model_module(pym)(self)(self.s_x)
        self.optimizer = pym.MMA(
            self.s_x, list(outputs), network,
            move=settings["move"], xmin=lower[self.free], xmax=upper[self.free],
            verbosity=0, mmaversion=self.version,
        )

    # ── Translation between the full design and pyMOTO's free variables ───────

    def _free(self, array):
        return np.asarray(array).reshape(-1, order="F")[self.free]

    def _expand(self, x_free):
        full = self.pinned.copy()
        full[self.free] = x_free
        return full.reshape(self.shape, order="F")

    def _responses(self, evaluation):
        """Objective, the volume budget, then each scenario constraint — as pyMOTO sees them.

        The objective is scaled to start at 10, whatever its units.  MMA's
        subproblem assumes objective and constraints of similar magnitude;
        without this, pyMOTO's subsolver stalls at its iteration cap every step
        (a volume objective near 100 beside constraints near 1 did exactly that).
        Toporia's own MMA scales the same way.  The factor is fixed from the
        first evaluation, so the problem does not change between iterations.
        """
        if self._objective_scale is None:
            self._objective_scale = 10.0 / max(abs(evaluation.objective), 1e-12)
        scale = self._objective_scale
        limit = self.model.volume_limit
        values = [scale * evaluation.objective, float(evaluation.volume / limit) - 1.0,
                  *(c.value for c in evaluation.constraints)]
        gradients = [scale * self._free(evaluation.objective_gradient),
                     self._free(evaluation.volume_gradient / limit),
                     *(self._free(c.gradient) for c in evaluation.constraints)]
        return values, gradients

    def _evaluate_free(self, x_free):
        """Evaluate the model at a free design; keep gradients for the adjoint pass."""
        values, self._gradients = self._responses(self.model.evaluate(self._expand(x_free)))
        return tuple(values)

    # ── The Updater interface ─────────────────────────────────────────────────

    def update(self, x, evaluation, completed):
        # The design has just been evaluated, so hand pyMOTO those numbers
        # rather than letting it evaluate the model a second time.
        values, gradients = self._responses(evaluation)
        x_free, _, _ = self.optimizer.step(x=self._free(x), g=np.array(values), dg=np.vstack(gradients))
        return self._expand(x_free)


class PymotoGCMMAUpdater(PymotoMMAUpdater):
    """pyMOTO's globally convergent MMA: re-evaluates trial designs until the step is safe."""

    name = "pymoto_gcmma"
    label = "GCMMA (pyMOTO)"
    order = 40
    version = "GCMMA"
