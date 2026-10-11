# plugins/updaters/conlin.py — CONLIN, convex linearisation.
#
# MMA's predecessor, and MMA with the asymptotes taken away.  Every function
# (the objective and each constraint) is linearised not in x but, variable by
# variable, in whichever of x or 1/x makes the approximation convex:
#
#     d f/d x_i >= 0   ->  term  d_i · x_i                 (linear in x)
#     d f/d x_i <  0   ->  term  (−d_i · x0_i²) / x_i      (linear in 1/x; the
#                                                           coefficient is positive: convex)
#
# plus a constant.  This is exactly MMA's approximation with the lower asymptote
# fixed at 0 and the upper one at infinity (mma.py moves them with the design's
# history instead; comparing the two shows what the asymptotes buy: they damp
# the step where the design oscillates and let the approximation stiffen or
# relax per variable, which CONLIN can only do through the move limit).
# Because the approximation is separable and convex, the subproblem
#
#     min  f~0(x)   s.t.  g~_j(x) <= 0,   alpha <= x <= beta     (bounds ∩ move limit)
#
# is solved through its dual.  For multipliers λ >= 0 the Lagrangian separates,
#
#     L_i(x_i) = c_i(λ) · x_i + r_i(λ) / x_i ,
#     c_i = Σ_j λ_j max(d_ij, 0) ,   r_i = x0_i² · Σ_j λ_j max(−d_ij, 0)   (j = 0 is the objective, λ_0 = 1)
#
# whose minimiser is x_i = sqrt(r_i / c_i) clipped to [alpha_i, beta_i].  The dual
# function W(λ) = min_x L is concave and its gradient is g~(x(λ)), so the m
# multipliers are found by bound-constrained maximisation (SciPy's L-BFGS-B),
# warm-started from the last iteration.  That handles any number of constraints,
# which a bisection on one multiplier (mma.py) does not.
#
# It works on the model's flat view (framework/optimisers/flat_view.py): free
# variables only, the volume budget as the first constraint, then the
# scenario's, and the objective rescaled to start at 10 so it is comparable with
# the normalised constraints.  Nothing damps the step but the move limit.
#
# References:
#   C. Fleury, V. Braibant, "Structural optimization: a new dual method using
#     mixed variables", IJNME 23 (1986) 409–428.
#   C. Fleury, "First and second order convex approximation strategies in
#     structural optimization", Struct. Optim. 1 (1989) 3–10.
#   K. Svanberg, "The method of moving asymptotes", IJNME 24 (1987) 359–373.

import numpy as np
from scipy.optimize import minimize

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater
from toporia.plugins.shared_params import MOVE


class ConlinUpdater(Updater):
    """CONLIN: convex linearisation in x or 1/x, solved through its dual, any number of constraints."""

    name = "conlin"
    label = "CONLIN (convex linearisation)"
    order = 25
    params = (
        MOVE,
        Param("conlin_lambda_max", 1e6, "Multiplier cap",
              "Upper bound on the dual multipliers. It matters only when a constraint cannot be met "
              "inside the move limit: the multiplier then runs to this value.",
              min=1.0, max=1e9, step=1e3, decimals=0),
    )
    max_constraints = None            # the dual is solved for any number of constraints
    schedulable = ("move",)
    flat_view = True
    flat_objective_scale = 10.0       # comparable with the normalised constraints, as for MMA

    def initialize(self, model, settings):
        self.model = model
        self.move = settings["move"]
        self.lambda_max = settings["conlin_lambda_max"]
        flat = self.flat_problem(model)
        self.lower, self.upper = flat.lower, flat.upper
        self.multipliers = None       # warm start for the dual between iterations

    def update(self, x, evaluation, completed):
        flat = self.flat
        flat.remember(x, evaluation)
        x0 = flat.reduce(x)
        g0 = flat.g(x0)
        grads = np.vstack([flat.df(x0), flat.dg(x0)])      # row 0 the objective, then the constraints
        m = g0.size
        if self.multipliers is None or self.multipliers.size != m:
            self.multipliers = np.zeros(m)

        # Move limits ∩ bounds.  The lower end stays positive: the 1/x terms need it.
        alpha = np.maximum(np.maximum(self.lower, x0 - self.move), 1e-6)
        beta = np.maximum(np.minimum(self.upper, x0 + self.move), alpha)

        # Coefficients of the parts linear in x and in 1/x, one row per function.
        linear = np.maximum(grads, 0.0)
        reciprocal = np.maximum(-grads, 0.0) * (x0 * x0)
        # The constant of g~_j is g_j minus the value of its x-dependent terms at x0.
        constants = g0 - (np.sum(linear[1:] * x0, axis=1) + np.sum(reciprocal[1:] / x0, axis=1))

        def minimiser(lam):
            weights = np.concatenate([[1.0], lam])
            c = weights @ linear
            r = weights @ reciprocal
            positive = c > 0.0
            # no cost in x: the reciprocal term alone pulls x up, to the upper limit
            x_new = np.where(positive, np.sqrt(r / np.where(positive, c, 1.0)), beta)
            return np.clip(x_new, alpha, beta)

        def constraints_at(x_new):
            """The approximated constraints g~_j(x_new); <= 0 is satisfied."""
            return linear[1:] @ x_new + reciprocal[1:] @ (1.0 / x_new) + constants

        def negative_dual(lam):
            x_new = minimiser(lam)
            g_approx = constraints_at(x_new)
            objective = linear[0] @ x_new + reciprocal[0] @ (1.0 / x_new)
            return -(objective + lam @ g_approx), -g_approx

        result = minimize(negative_dual, self.multipliers, jac=True, method="L-BFGS-B",
                          bounds=[(0.0, self.lambda_max)] * m,
                          options={"maxiter": 300, "ftol": 1e-14, "gtol": 1e-10})
        self.multipliers = np.clip(result.x, 0.0, self.lambda_max)
        return flat.expand(minimiser(self.multipliers))
