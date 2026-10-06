# plugins/updaters/mma.py — the method of moving asymptotes (MMA), one constraint.
#
# Mirrors the optimiser half of the top88mma.m script: a moving-asymptote
# convex approximation of the objective and of the normalised volume constraint
#
#     g(x) = V(x) / V_limit − 1  ≤  0,
#
# solved through its dual by bisection on the single multiplier.  The objective
# is rescaled by f0fac so its magnitude is comparable with the constraint.
#
# The subproblem works on the model's flat view (framework/optimisers/flat_view.py): the free design
# variables, column-major as in top88, with the volume budget as g_0.  Elements
# pinned by holes or solid rings are left out rather than moved and clipped back.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater
from toporia.plugins.shared_params import MOVE


class MMAUpdater(Updater):
    """Method of moving asymptotes for one volume constraint."""

    name = "mma"
    label = "Method of moving asymptotes"
    order = 20
    params = (
        MOVE,
        Param("mma_tol", 1e-4, "MMA tolerance",
              "MMA's own, stricter convergence test on the largest design change. "
              "The engine's tolerance still applies as well.",
              min=0.0, max=1.0, step=1e-4, decimals=6),
        Param("asyinit", 0.5, "Asymptote init", "Initial asymptote distance, as a fraction of the bounds.",
              min=0.01, max=1.0, step=0.05, decimals=2),
        Param("asyincr", 1.2, "Asymptote grow", "Asymptote expansion after consistent design motion.",
              min=1.0, max=2.0, step=0.05, decimals=2),
        Param("asydecr", 0.7, "Asymptote shrink", "Asymptote contraction after oscillating design motion.",
              min=0.1, max=1.0, step=0.05, decimals=2),
        Param("c", 1000.0, "Constraint scale", "Penalty scale on the volume constraint in the MMA subproblem.",
              min=1.0, max=1e6, step=100.0, decimals=0),
    )

    # The volume budget only: the subproblem's dual is solved by 1-D bisection.
    max_constraints = 0
    schedulable = ("move",)
    flat_view = True   # unscaled: f0fac below is MMA's own, iteration-dependent scaling

    def initialize(self, model, settings):
        self.model = model
        self.move = settings["move"]
        self.convtol = settings["mma_tol"]
        self.asyinit = settings["asyinit"]
        self.asyincr = settings["asyincr"]
        self.asydecr = settings["asydecr"]
        self.c_mma = settings["c"]

        flat = self.flat_problem(model)
        self.n = flat.n
        self.xmin = flat.lower
        self.xmax = flat.upper
        self.low = self.xmin.copy()
        self.upp = self.xmax.copy()
        self.xold1 = flat.x0.copy()
        self.xold2 = self.xold1.copy()
        self.f0fac = None

    def update(self, x, evaluation, completed):
        objective = evaluation.objective
        if self.f0fac is None:
            self.f0fac = 10.0 / max(abs(objective), 1e-12)
        elif completed >= 19 and self.f0fac * objective < 0.1:
            self.f0fac = 1.0 / max(abs(objective), 1e-12)

        flat = self.flat
        flat.remember(x, evaluation)
        xval = flat.reduce(x)
        df0dx = flat.df(xval) * self.f0fac
        fval = flat.g(xval)[0]        # the volume budget; MMA here enforces nothing else
        dfdx = flat.dg(xval)[0]

        xmma, self.low, self.upp = self._subproblem(xval, df0dx, fval, dfdx, completed)

        self.xold2 = self.xold1
        self.xold1 = xval.copy()
        return flat.expand(np.clip(xmma, self.xmin, self.xmax))

    def is_converged(self, change):
        """MMA's own, tighter tolerance (method.mma_tol), in addition to the engine's."""
        return change < self.convtol

    def _subproblem(self, xval, df0dx, fval, dfdx, completed):
        """Solve the one-constraint MMA approximation used for volume control."""
        n = self.n
        xmin, xmax = self.xmin, self.xmax
        xmamieps = 1e-5

        if completed < 2:
            low = xval - self.asyinit * (xmax - xmin)
            upp = xval + self.asyinit * (xmax - xmin)
        else:
            zzz = (xval - self.xold1) * (self.xold1 - self.xold2)
            factor = np.ones(n)
            factor[zzz > 0.0] = self.asyincr
            factor[zzz < 0.0] = self.asydecr
            low = xval - factor * (self.xold1 - self.low)
            upp = xval + factor * (self.upp - self.xold1)
            low = np.maximum(low, xval - 10.0 * (xmax - xmin))
            low = np.minimum(low, xval - 0.01 * (xmax - xmin))
            upp = np.minimum(upp, xval + 10.0 * (xmax - xmin))
            upp = np.maximum(upp, xval + 0.01 * (xmax - xmin))

        alpha = np.maximum(xmin, low + 0.1 * (xval - low))
        beta = np.minimum(xmax, upp - 0.1 * (upp - xval))
        alpha = np.maximum(alpha, xval - self.move)
        beta = np.minimum(beta, xval + self.move)

        ux1 = upp - xval
        xl1 = xval - low
        ux2 = ux1 * ux1
        xl2 = xl1 * xl1
        xmami = np.maximum(xmax - xmin, xmamieps)
        regularizer = 1e-5 * np.maximum(np.abs(df0dx), 1.0 / xmami)

        p0 = np.maximum(df0dx, 0.0) + regularizer
        q0 = np.maximum(-df0dx, 0.0) + regularizer
        p0 *= ux2
        q0 *= xl2

        p = np.maximum(dfdx, 0.0) + 1e-5 * np.maximum(np.abs(dfdx), 1.0 / xmami)
        q = np.maximum(-dfdx, 0.0) + 1e-5 * np.maximum(np.abs(dfdx), 1.0 / xmami)
        p *= ux2
        q *= xl2
        b = float(np.sum(p / ux1 + q / xl1) - fval)

        def candidate(lam):
            """The subproblem's minimiser for multiplier lam, inside the move limits."""
            plam = p0 + lam * p
            qlam = q0 + lam * q
            sqrtp = np.sqrt(np.maximum(plam, 0.0))
            sqrtq = np.sqrt(np.maximum(qlam, 0.0))
            x = (sqrtp * low + sqrtq * upp) / (sqrtp + sqrtq + 1e-30)
            return np.minimum(beta, np.maximum(alpha, x))

        def constraint_at(x):
            """The approximated volume constraint at x; ≤ 0 is satisfied."""
            return float(np.sum(p / (upp - x) + q / (x - low)) - b)

        x0 = candidate(0.0)
        if constraint_at(x0) <= 0.0:
            return x0, low, upp

        lam_low, lam_high = 0.0, 1.0
        while constraint_at(candidate(lam_high)) > 0.0 and lam_high < self.c_mma:
            lam_low = lam_high
            lam_high *= 2.0
        lam_high = min(lam_high, self.c_mma)

        for _ in range(80):
            lam = 0.5 * (lam_low + lam_high)
            x = candidate(lam)
            if constraint_at(x) > 0.0:
                lam_low = lam
            else:
                lam_high = lam
            if lam_high - lam_low < 1e-10 * (1.0 + lam_high):
                break

        return candidate(lam_high), low, upp
