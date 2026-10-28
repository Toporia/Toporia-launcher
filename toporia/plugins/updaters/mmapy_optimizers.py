# plugins/updaters/mmapy_optimizers.py — Svanberg's MMA and GCMMA through Arjen Deetman's `mmapy`.
#
# `mmapy` (https://github.com/arjendeetman/GCMMA-MMA-Python, PyPI "mmapy") is a
# line-by-line Python port of Krister Svanberg's reference MATLAB code.  That
# makes it the natural yardstick for Toporia's own MMA (mma.py, a bisection on
# one multiplier) and for pyMOTO's (pymoto_optimizers.py): three independent
# implementations of the same method should land on the same design.
#
# mmapy exposes the method as functions, not as a loop.  `mmasub` is called once
# per outer iteration with the values and gradients at the current design and
# returns the next one, so these are ordinary Updaters on the flat view
# (framework/optimisers/flat_view.py) — no background thread is needed:
#
#     engine: Evaluation at x ──> flat view: f, g, df, dg (free variables, volume first)
#                                     │
#            mmapy_mma:   mmasub(m, n, iter, x, ..., f0, df0, f, df, low, upp, ...)  ──> x_new
#            mmapy_gcmma: asymp -> gcmmasub -> [concheck -> raaupdate -> gcmmasub]*  ──> x_new
#
# GCMMA differs in one respect: its approximation is only accepted once it is
# "conservative" (it over-estimates the true functions at the new design), and
# when it is not, the outer iteration re-solves with a stiffer approximation —
# an inner iteration, each needing the functions at a trial design.  Those trial
# evaluations go through the flat view, which counts them (`solves`), and the
# last one is cached so the engine does not repeat it for the design it adopts.
#
# Conventions matched to mmapy's own example: arrays are column vectors,
# a0 = 1, a_i = 0 and c_i = 1000, d_i = 0 (so the constraints are enforced
# almost as hard constraints), iteration numbers start at 1.  The objective is
# scaled to start at 10 (flat_objective_scale), as for pyMOTO, because MMA's
# subproblem assumes objective and constraints of similar magnitude.
#
# Licence — read this before redistributing
# -----------------------------------------
# mmapy is GPL-3.  Toporia is Apache-2.0.  mmapy is therefore NEVER bundled and
# never required: it is imported inside initialize(), declared in `dependencies`
# so the pickers grey the updaters out when it is missing, and installed by the
# user separately:  pip install "toporia[mmapy]"  (or  pip install mmapy).
#
# References
# ----------
# K. Svanberg, "The method of moving asymptotes — a new method for structural
#   optimization", Int. J. Numer. Meth. Engng 24 (1987) 359-373.
# K. Svanberg, "A class of globally convergent optimization methods based on
#   conservative convex separable approximations", SIAM J. Optim. 12 (2002) 555-573.

import numpy as np

from toporia.framework.parts.updater import Updater
from toporia.plugins.shared_params import MOVE

IMPORT_HINT = (
    "mmapy is not installed.  It is GPL-3 licensed, so Toporia (Apache-2.0) does not ship it: "
    'install it yourself with  pip install "toporia[mmapy]"  or  pip install mmapy.'
)


def import_mmapy():
    """Import mmapy, or explain how to install it.  The only place it is imported."""
    try:
        import mmapy
    except ModuleNotFoundError as exc:
        if exc.name != "mmapy":
            raise
        raise ImportError(IMPORT_HINT) from exc
    return mmapy


def _column(values):
    """A vector as the (k, 1) column array mmapy works with."""
    return np.asarray(values, dtype=float).reshape(-1, 1)


class MmapyMMAUpdater(Updater):
    """Svanberg's method of moving asymptotes, as ported by mmapy, with any number of constraints."""

    name = "mmapy_mma"
    reference = (
        'K. Svanberg, "The method of moving asymptotes", Int. J. Numer. Meth. Eng. 24 (1987) '
        '359-373, through the mmapy Python port by A. Deetman '
        '(github.com/arjendeetman/GCMMA-MMA-Python, GPL-3).'
        ' Papers: https://doi.org/10.1002/nme.1620240207'
    )
    label = "MMA (mmapy)"
    use_when = "Svanberg's MMA with any number of constraints, via the mmapy package (GPL, optional)."
    order = 32
    params = (MOVE,)
    max_constraints = None   # mmasub takes m constraints
    dependencies = ("mmapy",)
    flat_view = True
    flat_objective_scale = 10.0

    def initialize(self, model, settings):
        self.mmapy = import_mmapy()
        self.move = settings["move"]
        flat = self.flat_problem(model)
        self.n, self.m = flat.n, flat.m
        self.xmin, self.xmax = _column(flat.lower), _column(flat.upper)
        self.xold1 = _column(flat.x0)
        self.xold2 = self.xold1.copy()
        self.low, self.upp = self.xmin.copy(), self.xmax.copy()
        # mmapy's example values: the y_i variables (constraint violation) cost 1000 each.
        self.a0 = 1.0
        self.a = np.zeros((self.m, 1))
        self.c = 1000.0 * np.ones((self.m, 1))
        self.d = np.zeros((self.m, 1))

    def update(self, x, evaluation, completed):
        # The design has just been evaluated: hand mmapy those numbers, not a second solve.
        flat = self.flat
        flat.remember(x, evaluation)
        xval = flat.reduce(x)
        result = self.mmapy.mmasub(
            self.m, self.n, completed + 1, _column(xval), self.xmin, self.xmax,
            self.xold1, self.xold2, flat.f(xval), _column(flat.df(xval)), _column(flat.g(xval)),
            flat.dg(xval), self.low, self.upp, self.a0, self.a, self.c, self.d, move=self.move,
        )
        xmma, self.low, self.upp = result[0], result[-2], result[-1]
        self.xold2, self.xold1 = self.xold1, _column(xval)
        return flat.expand(np.clip(xmma.ravel(), flat.lower, flat.upper))


class MmapyGCMMAUpdater(Updater):
    """Svanberg's globally convergent MMA, as ported by mmapy: inner iterations until conservative."""

    name = "mmapy_gcmma"
    reference = (
        'K. Svanberg, "A class of globally convergent optimization methods based on '
        'conservative convex separable approximations", SIAM J. Optim. 12 (2002) 555-573, '
        'through the mmapy Python port by A. Deetman '
        '(github.com/arjendeetman/GCMMA-MMA-Python, GPL-3).'
        ' Papers: https://doi.org/10.1137/S1052623499362822'
    )
    label = "GCMMA (mmapy)"
    use_when = "Globally convergent MMA via mmapy, when plain MMA oscillates (GPL, optional)."
    order = 42
    params = (MOVE,)
    max_constraints = None
    dependencies = ("mmapy",)
    flat_view = True
    flat_objective_scale = 10.0

    #: Svanberg's cap on inner iterations per outer iteration.
    max_inner = 15
    epsimin = 1e-7
    raa0eps = 1e-6
    raaeps = 1e-6

    def initialize(self, model, settings):
        self.mmapy = import_mmapy()
        flat = self.flat_problem(model)
        self.n, self.m = flat.n, flat.m
        self.xmin, self.xmax = _column(flat.lower), _column(flat.upper)
        self.xold1 = _column(flat.x0)
        self.xold2 = self.xold1.copy()
        self.low, self.upp = self.xmin.copy(), self.xmax.copy()
        self.raa0 = 0.01
        self.raa = 0.01 * np.ones((self.m, 1))
        self.a0 = 1.0
        self.a = np.zeros((self.m, 1))
        self.c = 1000.0 * np.ones((self.m, 1))
        self.d = np.zeros((self.m, 1))
        self.inner_total = 0     # trial designs evaluated beyond the one per outer iteration
        self.outer_total = 0

    def _subproblem(self, xval, f0val, df0dx, fval, dfdx, outer):
        """Build the asymptotes and solve the convex approximation with the current raa0, raa."""
        mm = self.mmapy
        self.low, self.upp, self.raa0, self.raa = mm.asymp(
            outer, self.n, xval, self.xold1, self.xold2, self.xmin, self.xmax, self.low, self.upp,
            self.raa0, self.raa, self.raa0eps, self.raaeps, df0dx, dfdx)
        return self._solve(xval, f0val, df0dx, fval, dfdx, outer)

    def _solve(self, xval, f0val, df0dx, fval, dfdx, outer):
        out = self.mmapy.gcmmasub(
            self.m, self.n, outer, self.epsimin, xval, self.xmin, self.xmax, self.low, self.upp,
            self.raa0, self.raa, f0val, df0dx, fval, dfdx, self.a0, self.a, self.c, self.d)
        return out[0], out[-2], out[-1]          # x, f0app, fapp

    def update(self, x, evaluation, completed):
        mm, flat = self.mmapy, self.flat
        flat.remember(x, evaluation)
        free = flat.reduce(x)
        xval = _column(free)
        f0val = np.array([[flat.f(free)]])
        fval = _column(flat.g(free))
        df0dx, dfdx = _column(flat.df(free)), flat.dg(free)

        outer = completed + 1
        xmma, f0app, fapp = self._subproblem(xval, f0val, df0dx, fval, dfdx, outer)

        # Is the approximation conservative at the point it proposes?  If not, make it
        # stiffer (raaupdate) and solve again; each check costs one evaluation of the model.
        f0new, fnew = self._evaluate(xmma)
        inner = 0
        while not mm.concheck(self.m, self.epsimin, f0app, f0new, fapp, fnew) and inner < self.max_inner:
            inner += 1
            self.raa0, self.raa = mm.raaupdate(
                xmma, xval, self.xmin, self.xmax, self.low, self.upp, f0new, fnew, f0app, fapp,
                self.raa0, self.raa, self.raa0eps, self.raaeps, self.epsimin)
            xmma, f0app, fapp = self._solve(xval, f0val, df0dx, fval, dfdx, outer)
            f0new, fnew = self._evaluate(xmma)

        self.inner_total += inner
        self.outer_total += 1
        self.xold2, self.xold1 = self.xold1, xval.copy()
        return flat.expand(np.clip(xmma.ravel(), flat.lower, flat.upper))

    def _evaluate(self, xcol):
        """The model's objective and constraints at a trial design (cached by the flat view)."""
        free = np.clip(xcol.ravel(), self.flat.lower, self.flat.upper)
        return np.array([[self.flat.f(free)]]), _column(self.flat.g(free))

    def cached_evaluation(self, design):
        """The last trial design is the one adopted, and it was just evaluated: reuse that."""
        return self.flat.cached(self.flat.reduce(design))

    def report(self):
        """How much extra work the inner iterations cost, for run.json."""
        return {"optimiser": self.label, "outer_iterations": self.outer_total,
                "inner_iterations": self.inner_total}
