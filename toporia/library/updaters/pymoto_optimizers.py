# library/updaters/pymoto_optimizers.py — pyMOTO's MMA and GCMMA as updaters.
#
# pyMOTO's optimisers expect a pyMOTO network.  To drive ANY Toporia model with
# them, the model is presented to pyMOTO as a single module:
#
#     pyMOTO Signal x_free ──[_ToporiaModel]──> objective, volume constraint
#                               │
#                               └─ calls model.evaluate() and hands back its gradients
#
# so pyMOTO's MMA — or its globally convergent GCMMA, which re-evaluates the
# model at trial designs inside an iteration — can move a design whose physics
# it knows nothing about.
#
# Only the free variables are handed to pyMOTO.  Elements pinned by passive or
# void regions have equal lower and upper bounds, and pyMOTO's MMA divides by
# that range; leaving them out keeps it well defined and changes nothing,
# because a pinned variable cannot move anyway.
#
# Requires the optional dependency:  pip install "toporia[pymoto]"

import numpy as np

from toporia.core.composition import Updater
from toporia.library.models.pymoto_compliance import import_pymoto

from ._common import MOVE

_module_class = None


def _model_module(pym):
    """Build (once) the pyMOTO Module that wraps a Toporia model.  Lazy: pyMOTO is optional."""
    global _module_class
    if _module_class is None:

        class _ToporiaModel(pym.Module):
            """A Toporia model seen by pyMOTO: free design -> (objective, volume constraint)."""

            def __init__(self, updater):
                self.updater = updater

            def __call__(self, x_free):
                return self.updater._evaluate_free(x_free)

            def _sensitivity(self, d_objective, d_constraint):
                updater = self.updater
                gradient = np.zeros_like(updater._objective_gradient)
                if d_objective is not None:
                    gradient = gradient + d_objective * updater._objective_gradient
                if d_constraint is not None:
                    gradient = gradient + d_constraint * updater._constraint_gradient
                return gradient

        _module_class = _ToporiaModel
    return _module_class


class PymotoMMAUpdater(Updater):
    """pyMOTO's method of moving asymptotes (Svanberg 2007 variant)."""

    name = "pymoto_mma"
    label = "MMA (pyMOTO)"
    order = 30
    params = (MOVE,)
    version = "MMA2007"   # pyMOTO's mmaversion: "MMA1987", "MMA2007" or "GCMMA"

    def initialize(self, model, settings):
        pym = import_pymoto()
        self.model = model
        lower, upper = model.bounds()
        self.shape = lower.shape
        lower, upper = lower.reshape(-1, order="F"), upper.reshape(-1, order="F")
        self.free = upper > lower
        self.pinned = lower.copy()   # a pinned element sits at its (equal) bounds

        start = model.initial_design().reshape(-1, order="F")[self.free]
        self.s_x = pym.Signal("x", start.copy(), min=lower[self.free], max=upper[self.free])
        with pym.Network() as network:
            s_objective, s_constraint = _model_module(pym)(self)(self.s_x)
        self.optimizer = pym.MMA(
            self.s_x, [s_objective, s_constraint], network,
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

    def _constraint(self, evaluation):
        limit = self.model.volume_limit
        return float(evaluation.volume / limit) - 1.0, evaluation.volume_gradient / limit

    def _evaluate_free(self, x_free):
        """Evaluate the model at a free design; keep gradients for the adjoint pass."""
        evaluation = self.model.evaluate(self._expand(x_free))
        constraint, constraint_gradient = self._constraint(evaluation)
        self._objective_gradient = self._free(evaluation.objective_gradient)
        self._constraint_gradient = self._free(constraint_gradient)
        return evaluation.objective, constraint

    # ── The Updater interface ─────────────────────────────────────────────────

    def update(self, x, evaluation, completed):
        # The design has just been evaluated, so hand pyMOTO those numbers
        # rather than letting it evaluate the model a second time.
        constraint, constraint_gradient = self._constraint(evaluation)
        responses = np.array([evaluation.objective, constraint])
        gradients = np.vstack([self._free(evaluation.objective_gradient), self._free(constraint_gradient)])
        x_free, _, _ = self.optimizer.step(x=self._free(x), g=responses, dg=gradients)
        return self._expand(x_free)


class PymotoGCMMAUpdater(PymotoMMAUpdater):
    """pyMOTO's globally convergent MMA: re-evaluates trial designs until the step is safe."""

    name = "pymoto_gcmma"
    label = "GCMMA (pyMOTO)"
    order = 40
    version = "GCMMA"
