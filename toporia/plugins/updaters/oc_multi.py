# plugins/updaters/oc_multi.py — optimality criteria with several constraints.
#
# oc.py finds ONE multiplier, for the volume.  With constraints g_j <= 0
# (j = 0 the volume budget, then the scenario's, e.g. a stress limit) the
# Lagrangian's stationarity gives the same kind of fixed-point rule with a sum:
#
#     x_new_i = clip( x_i · ( max(−dC/dx_i, 0) ÷ D_i )^η ,  x ± move,  [lower, upper] ),
#     D_i     = Σ_j λ_j · dg_j/dx_i ,       λ_j >= 0,   η = 1/2,
#
# which for a single volume constraint is exactly oc.py (the volume gradient is
# positive, so D_i = λ · dV/dx_i).  The multipliers must satisfy complementarity,
#
#     g_j(x_new) <= 0,   λ_j >= 0,   λ_j · g_j(x_new) = 0 ,
#
# and are found here by cycling through the constraints (Gauss–Seidel): for one j
# at a time, hold the others fixed and bisect λ_j so that g_j(x_new) = 0, or set
# it to 0 if that constraint is already satisfied.  Raising λ_j lowers x where
# dg_j/dx > 0 and raises it where dg_j/dx < 0, which lowers the linearised g_j
# either way, so each one-dimensional search is monotone.  The volume is
# evaluated exactly (model.volume_of, no solve); every other constraint through
# its linearisation g_j + ∇g_j·(x_new − x), because evaluating it needs a solve.
#
# Which constraints this is honest for.  The classical rule (Zhou & Rozvany 1991;
# Yin & Yang 2001) assumes every sensitivity in D_i has the sign of the volume's:
# material costs and never helps a constraint.  A stress limit is not like that,
# its sensitivity changes sign from element to element (adding material to one
# element can relieve a neighbour).  Where D_i <= 0 the rule has no finite
# answer; here the element goes to its upper limit when the objective also wants
# material (−dC/dx > 0) and to its lower limit otherwise: more material helps
# both functions in the first case, and nothing asks for it in the second.  This
# is a safeguard, not a proof of convergence: with sign-changing constraints OC is
# a heuristic, may oscillate, and enforces the limit only as well as the move
# limit keeps the linearisation valid.  Use a small move limit for those, and
# prefer MMA/CONLIN-type updaters when the constraint is the point.
# It minimises compliance only (the update needs −dC/dx >= 0 to be a ratio), and,
# like oc.py, needs one density per element.
#
# It works on the model's flat view (framework/optimisers/flat_view.py), which
# supplies the constraints and their gradients already normalised
# (g_0 = V/V_limit − 1), so the multipliers of different constraints are comparable.
#
# References:
#   M. Zhou, G. I. N. Rozvany, "The COC algorithm, Part II: Topological, geometrical
#     and generalized shape optimization", CMAME 89 (1991) 309–336; and
#     "DCOC: an optimality criteria method for large systems", Struct. Optim. 5
#     (1992) 12–25 (the multi-constraint extension).
#   Q. Yin, W. Yang, "Topology optimization based on the optimality criteria method under
#     multiple constraints", Comput. Struct. 79 (2001) 1839–1850.
#   O. Sigmund, "A 99 line topology optimization code written in Matlab", SMO 21
#     (2001) 120–127 (the single-constraint rule in oc.py).

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater
from toporia.plugins.shared_params import MOVE


class MultiConstraintOC(Updater):
    """Optimality criteria with a multiplier per constraint, found by cyclic bisection."""

    name = "oc_multi"
    reference = (
        'Optimality criteria with one multiplier per constraint, after M. Zhou and G. I. N. '
        'Rozvany, "The COC algorithm, Part II: Topological, geometrical and generalized shape '
        'optimization", Comput. Methods Appl. Mech. Eng. 89 (1991) 309-336; Toporia\'s own '
        'version.'
        ' Papers: https://doi.org/10.1016/0045-7825%2891%2990046-9'
    )
    label = "Optimality criteria, several constraints"
    use_when = (
        "OC's simplicity with extra constraints, one multiplier each; compliance objective and element "
        "densities only."
    )
    order = 15
    params = (
        MOVE,
        Param("oc_eta", 0.5, "Damping exponent",
              "Exponent η of the update ratio; 0.5 is the classical choice. Smaller is more cautious.",
              min=0.1, max=1.0, step=0.05, decimals=2),
        Param("oc_sweeps", 30, "Multiplier sweeps",
              "Largest number of passes over the constraints when searching for the multipliers.",
              min=1, max=200),
    )
    schedulable = ("move",)

    # Compliance only, as for oc.py; any number of further constraints (see the header
    # on what that means when their sensitivities change sign).
    objectives = ("compliance",)
    max_constraints = None
    flat_view = True
    needs_element_densities = True

    def initialize(self, model, settings):
        self.model = model
        self.move = settings["move"]
        self.eta = settings["oc_eta"]
        self.sweeps = int(settings["oc_sweeps"])
        flat = self.flat_problem(model)
        self.lower, self.upper = flat.lower, flat.upper
        self.multipliers = None

    def update(self, x, evaluation, completed):
        flat = self.flat
        flat.remember(x, evaluation)
        x0 = flat.reduce(x)
        g0 = flat.g(x0)
        dg = flat.dg(x0)
        pull = np.maximum(-flat.df(x0), 0.0)           # how much the objective wants material here
        m = g0.size
        if self.multipliers is None or self.multipliers.size != m:
            self.multipliers = np.zeros(m)
        low = np.maximum(self.lower, x0 - self.move)
        high = np.minimum(self.upper, x0 + self.move)
        tiny = 1e-30

        def candidate(lam):
            denominator = lam @ dg
            usable = denominator > tiny
            ratio = np.where(usable, pull / np.where(usable, denominator, 1.0), 0.0)
            x_new = x0 * ratio ** self.eta
            # No finite answer where the constraints' combined sensitivity is not positive.
            x_new = np.where(usable, x_new, np.where(pull > 0.0, high, low))
            return np.clip(x_new, low, high)

        def violation(j, x_new):
            """g_j at the candidate: the volume exactly, the others through their linearisation."""
            if j == 0:
                return self.model.volume_of(flat.expand(x_new)) / self.model.volume_limit - 1.0
            return float(g0[j] + dg[j] @ (x_new - x0))

        lam = self.multipliers.copy()
        for _ in range(self.sweeps):
            moved = 0.0
            for j in range(m):
                before = lam[j]
                lam[j] = 0.0
                if violation(j, candidate(lam)) > 0.0:
                    lo, hi = 0.0, max(before, 1.0)
                    while hi < 1e30:
                        lam[j] = hi
                        if violation(j, candidate(lam)) <= 0.0:
                            break
                        lo, hi = hi, hi * 4.0
                    for _ in range(80):
                        mid = 0.5 * (lo + hi)
                        lam[j] = mid
                        if violation(j, candidate(lam)) > 0.0:
                            lo = mid
                        else:
                            hi = mid
                        if hi - lo < 1e-10 * hi:
                            break
                    lam[j] = hi
                moved = max(moved, abs(lam[j] - before) / (abs(before) + abs(lam[j]) + 1e-30))
            if moved < 1e-6:
                break
        self.multipliers = lam
        return flat.expand(candidate(lam))
