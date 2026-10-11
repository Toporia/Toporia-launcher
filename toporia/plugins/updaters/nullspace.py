# plugins/updaters/nullspace_optimizer.py — Feppon's null-space optimiser, wrapped as an updater.
#
# The null-space method (Feppon, Allaire & Dapogny) was designed for level-set
# and shape optimisation with many constraints.  It integrates an ODE: at each
# step the design moves along  -alpha_J * xi_J - alpha_C * xi_C,  where
#
#     xi_J  is the objective's descent direction projected onto the null space of
#           the ACTIVE constraints, so it does not disturb them at first order;
#     xi_C  is a Gauss-Newton step that pulls violated or nearly-active
#           constraints back to feasibility.
#
# Constraints are therefore followed rather than penalised: the iterates track
# the feasible set closely, and constraints that are far from active are ignored.
# That suits Toporia's second constraints (a stress limit beside the volume
# budget) as well as the volume budget alone.
#
# The library runs its own loop (nlspace_solve), so this is an ExternalOptimizer
# (framework/optimisers/external_loop.py), shaped like scipy_slsqp.py:
#
#     flat.x0, f, df            ──>  Optimizable.x0, J, dJ        ──> nlspace_solve(problem, params)
#     flat.g, flat.dg  (g <= 0) ──>  H, dH   (inequalities h <= 0, as the library wants)
#     flat.lower, flat.upper    ──>  bound_constraints_optimizable (see below)
#     iterate                   <──  Optimizable.accept, once per accepted point
#     Verdict                   <──  the last ||dx|| against its tolerance
#
# Bounds.  The library has no bound argument.  Its documented route is the
# decorator bound_constraints_optimizable(l, u), which appends  l - x <= 0  and
# x - u <= 0  to the inequality constraints AND clips every trial point back into
# the box in retract().  That is what is used here.  The price is 2n extra
# inequality rows, but only those within a small distance of being active are
# "felt" by the QP, so it stays workable on coarse meshes.
#
# The library calls accept() at the START of every iteration, the first time on
# the starting design the engine already has; that first call is not reported.
#
# Licence — read this before redistributing
# -----------------------------------------
# nullspace_optimizer is GPL-3.  Toporia is Apache-2.0.  The library is therefore
# NEVER bundled and never required: it is imported inside run(), declared in
# `dependencies` so the pickers grey this updater out when it is missing, and
# installed by the user separately:  pip install "toporia[nullspace]"  (or
# pip install nullspace_optimizer).
#
# Reference
# ---------
# F. Feppon, G. Allaire, C. Dapogny, "Null space gradient flows for constrained
#   optimization with applications to shape optimization", ESAIM: COCV 26 (2020) 90.
#   https://gitlab.com/florian.feppon/null-space-optimizer

import warnings

import numpy as np

from toporia.framework.optimisers.external_loop import ExternalOptimizer, Verdict
from toporia.framework.params import Param

IMPORT_HINT = (
    "nullspace_optimizer is not installed.  It is GPL-3 licensed, so Toporia (Apache-2.0) does not "
    'ship it: install it yourself with  pip install "toporia[nullspace]"  or  pip install nullspace_optimizer.'
)


def import_nullspace():
    """Import nullspace_optimizer, or explain how to install it.  The only place it is imported."""
    try:
        import nullspace_optimizer
    except ModuleNotFoundError as exc:
        if exc.name != "nullspace_optimizer":
            raise
        raise ImportError(IMPORT_HINT) from exc
    # The library calls OSQP with options OSQP has since renamed, which warns on every
    # QP solve (hundreds per run).  Silence only those, only from OSQP itself.
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"osqp\.")
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning, module=r"osqp\.")
    return nullspace_optimizer


def _flat_optimizable(nso, flat, iterate):
    """The library's Optimizable for a FlatProblem (built on demand: the library is optional)."""

    class _FlatOptimizable(nso.EuclideanOptimizable):
        """J, dJ and the inequality constraints H <= 0 of a FlatProblem; no equalities."""

        def __init__(self):
            self.reported = 0

        def x0(self):
            return flat.x0.copy()

        def J(self, x):
            return flat.f(x)

        def dJ(self, x):
            return flat.df(x)

        def H(self, x):
            return flat.g(x)

        def dH(self, x):
            return flat.dg(x)

        def accept(self, params, results):
            # Called at the start of every iteration, the first on the design the engine
            # already holds; report the later ones, each a design the engine has not seen.
            self.reported += 1
            if self.reported > 1:
                iterate(np.array(results["x"][-1], dtype=float))

    return _FlatOptimizable


class NullspaceUpdater(ExternalOptimizer):
    """Feppon's null-space optimiser: constraints followed, not penalised; any number of them."""

    name = "nullspace"
    label = "Null-space optimiser"
    order = 80
    dependencies = ("nullspace_optimizer",)
    params = (
        Param("nullspace_dt", 0.2, "Time step",
              "The null-space method integrates an ODE; this is its step. The largest change of any "
              "element per iteration is about alphaJ x dt, so it plays the role of a move limit.",
              min=0.005, max=1.0, step=0.01, decimals=3),
        Param("nullspace_maxit", 1000, "Null-space iterations",
              "The library's own iteration limit. The engine's limit and tolerance apply as well, "
              "whichever stops first.", min=1, max=100000),
        Param("nullspace_normalise", 50, "Normalised iterations",
              "For this many iterations the step is rescaled to its full length (the library's "
              "'itnormalisation'), however small the gradient has become; after it the step may only "
              "shrink. Longer is faster early on but leaves less time to settle.", min=1, max=10000),
        Param("nullspace_tol", 1e-5, "Null-space tolerance",
              "Stops when the step is shorter than this times the time step (the library's 'tol').",
              min=1e-9, max=1e-1, step=1e-6, decimals=9),
    )
    max_constraints = None          # every constraint goes to the library
    flat_objective_scale = 1.0      # the step is normalised, so the scale only needs to be sane
    reports = "iteration"           # accept() is called once per accepted point

    def run(self, flat, x0, iterate):
        nso = import_nullspace()
        problem_class = nso.bound_constraints_optimizable(flat.lower, flat.upper)(
            _flat_optimizable(nso, flat, iterate))
        dt = self.settings["nullspace_dt"]
        tolerance = self.settings["nullspace_tol"] * dt
        results = nso.nlspace_solve(problem_class(), {
            "dt": dt, "maxit": int(self.settings["nullspace_maxit"]), "tol": tolerance,
            "itnormalisation": int(self.settings["nullspace_normalise"]),
            "qp_solver_options": {"polishing": 0},   # polishing only prints a note
            "debug": -2,      # silent: the engine's console is the place for progress
        })
        step = float(results["||dx||"][-1])
        done = step <= tolerance
        message = (f"converged: step {step:.2g} <= tolerance {tolerance:.2g}" if done
                   else f"stopped at the iteration limit with step {step:.2g}")
        return Verdict(success=done, message=message, x=np.asarray(results["x"][-1], dtype=float),
                       iterations=int(results["it"][-1]), evaluations=int(flat.evaluations))
