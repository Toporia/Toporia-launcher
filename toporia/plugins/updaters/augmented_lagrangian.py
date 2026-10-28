# plugins/updaters/augmented_lagrangian.py — the outer loop of the augmented-Lagrangian method for local constraints.
#
# A scenario constraint of a response that offers `update_multipliers`
# (plugins/responses/local_stress.py) is not one number to keep below zero but
# a whole set of element constraints, summed into an augmented-Lagrangian penalty P
# with its own multipliers.  This updater minimises  J = f/f₀ + ΣP  with the
# moving-asymptote steps of mma.py (move limits, the volume budget as the one
# constraint MMA enforces itself), and every `inner` iterations calls
# update_multipliers on each such response (λ ← λ + μ h, μ ← min(α μ, μ_max)):
# the sequence of bound-constrained subproblems of PolyStress.
#
# The objective is divided by its first value f₀, so the penalty (which is
# normalised by the number of constraints) is comparable with it on every problem.
#
# Nothing in the framework changed for this: the updater reaches the responses
# through the model it is given (model.constraints, as AssembledModel keeps them)
# and the response owns its multipliers.

import numpy as np

from toporia.framework.params import Param
from toporia.plugins.updaters.mma import MMAUpdater


class AugmentedLagrangianUpdater(MMAUpdater):
    """MMA steps on f + the augmented-Lagrangian penalty, with outer multiplier updates."""

    name = "augmented_lagrangian"
    label = "Augmented Lagrangian (local constraints)"
    use_when = "For many local constraints at once (one per element), such as local stress."
    reference = (
        'O. Giraldo-Londono, G. H. Paulino, "PolyStress: a Matlab implementation for local'
        ' stress-constrained topology optimization using the augmented Lagrangian method",'
        ' Struct. Multidisc. Optim. 63 (2021) 2065-2097; the inner steps are Svanberg\'s MMA.'
        ' Papers: https://doi.org/10.1007/s00158-020-02760-8 https://doi.org/10.1007/s00158-010-0594-7'
    )
    order = 25
    params = MMAUpdater.params + (
        Param("inner", 5, "Iterations per multiplier update",
              "Design steps taken on each bound-constrained subproblem before the multipliers move.",
              min=1, max=100, step=1, decimals=0),
        Param("growth", 1.5, "Penalty growth α",
              "The penalty μ is multiplied by this at each multiplier update, up to its maximum.",
              min=1.0, max=10.0, step=0.1, decimals=2),
    )

    objectives = ("volume", "compliance")
    max_constraints = None
    constraints = ("local_stress",)
    schedulable = ("move",)

    def initialize(self, model, settings):
        super().initialize(model, settings)
        self.inner = int(settings["inner"])
        self.growth = settings["growth"]
        constraints = getattr(model, "constraints", [])
        self.local = [r for r in constraints if hasattr(r, "update_multipliers")]
        if len(self.local) != len(constraints):
            raise ValueError("The augmented-Lagrangian updater can only enforce constraints with "
                             "multipliers (local stress); other constraints are not handled.")
        self.scale = None

    def update(self, x, evaluation, completed):
        if self.scale is None:
            self.scale = max(abs(float(evaluation.objective)), 1e-30)
        flat = self.flat
        flat.remember(x, evaluation)
        xval = flat.reduce(x)
        # J = f/f₀ + ΣP and its gradient; the volume budget stays MMA's own constraint.
        value = evaluation.objective / self.scale + sum(c.value for c in evaluation.constraints)
        grad = evaluation.objective_gradient / self.scale
        for c in evaluation.constraints:
            grad = grad + c.gradient
        if self.f0fac is None:
            self.f0fac = 10.0 / max(abs(value), 1e-12)
        df0dx = flat.reduce(grad) * self.f0fac
        fval = flat.g(xval)[0]
        dfdx = flat.dg(xval)[0]

        xmma, self.low, self.upp = self._subproblem(xval, df0dx, fval, dfdx, completed)
        self.xold2 = self.xold1
        self.xold1 = xval.copy()

        if (completed + 1) % self.inner == 0:
            for response in self.local:
                response.update_multipliers(self.growth)
        return flat.expand(np.clip(xmma, self.xmin, self.xmax))

    def is_converged(self, change):
        """Never before the multipliers have had a chance to act: a still design is not yet feasible."""
        return False
