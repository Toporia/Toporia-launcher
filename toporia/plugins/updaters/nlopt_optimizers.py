# plugins/updaters/nlopt_optimizers.py — the gradient-based, constrained algorithms of NLopt.
#
# NLopt (Johnson, https://nlopt.readthedocs.io) is one C library with a common interface
# to dozens of optimisers.  This file wraps the four that make sense for topology
# optimisation: they use gradients, accept bounds, and take any number of nonlinear
# inequality constraints, so they enforce the volume budget and any further limit
# (stress, displacement) the scenario adds.
#
#     nlopt_mma     LD_MMA     method of moving asymptotes (Svanberg 1987/2002)
#     nlopt_ccsaq   LD_CCSAQ   conservative convex separable approximations with a
#                              quadratic model (Svanberg 2002) — MMA's globally
#                              convergent relative
#     nlopt_slsqp   LD_SLSQP   sequential least-squares QP (Kraft 1988); dense, so
#                              coarse meshes only
#     nlopt_auglag  AUGLAG     augmented Lagrangian (Conn, Gould & Toint 1991; Birgin &
#                              Martínez 2008) around a local L-BFGS
#
# NLopt runs its own loop and has no per-iteration callback.  So, as for SciPy's SLSQP
# (scipy_slsqp.py, the template), ExternalOptimizer runs the library in a background
# thread (framework/optimisers/external_loop.py) on the flat view
# (framework/optimisers/flat_view.py); the difference is *where* the engine is told about
# a new design: from inside the objective wrapper, once per evaluation
# (`reports = "evaluation"`).  An "iteration" in the live display is therefore one NLopt
# function evaluation.  Evaluations that land almost on top of the last one shown (trial
# points of the inner loops) are not shown, see `nlopt_report_step`: the engine ends a run
# when a shown step changes the design by less than its tolerance, and without this
# filter one such micro-step stops NLopt long before it has converged.
#
#     Toporia                         this adapter                NLopt
#     -------                         ------------                -----
#     flat.x0, lower, upper    ──>    x0, set_*_bounds        ──> opt.optimize(x0)
#     flat.f, flat.df          ──>    objective(x, grad)      <── (grad filled in place)
#     flat.g, flat.dg          ──>    add_inequality_mconstraint(c(result, x, grad))
#                                                                  NLopt wants g <= 0,
#                                                                  Toporia's own convention
#     iterate                  <──    after each evaluation   <──  (no callback exists)
#     Verdict                  <──    result code, numevals
#
# Install with `pip install nlopt` (or `pip install toporia[nlopt]`); without it these
# updaters are listed greyed out.
#
# References
# ----------
# S. G. Johnson, The NLopt nonlinear-optimization package, https://github.com/stevengj/nlopt
# K. Svanberg, "The method of moving asymptotes", IJNME 24 (1987) 359-373.
# K. Svanberg, "A class of globally convergent optimization methods based on conservative
#     convex separable approximations", SIAM J. Optim. 12 (2002) 555-573.
# D. Kraft, "A software package for sequential quadratic programming", DFVLR-FB 88-28, 1988.
# A. R. Conn, N. I. M. Gould, P. L. Toint, "A globally convergent augmented Lagrangian
#     algorithm for optimization with general constraints and simple bounds",
#     SIAM J. Numer. Anal. 28 (1991) 545-572.
# E. G. Birgin, J. M. Martínez, "Improving ultimate convergence of an augmented Lagrangian
#     method", Optim. Methods Softw. 23 (2008) 177-195.

import numpy as np

from toporia.framework.optimisers.external_loop import ExternalOptimizer, Verdict
from toporia.framework.params import Param

#: Constraint tolerance NLopt uses to decide a point is feasible.  Constraints are
#: normalised (volume is V / V_limit - 1), so an absolute 1e-8 is a tight, sensible value.
CONSTRAINT_TOLERANCE = 1e-8


class NLoptOptimizer(ExternalOptimizer):
    """Adapter for one NLopt algorithm; subclasses only name the algorithm.

    A subclass sets `algorithm` to the attribute name in the nlopt module
    (e.g. "LD_MMA").  This base has no `name`, so it is not itself registered.
    """

    dependencies = ("nlopt",)
    params = (
        Param("nlopt_maxeval", 500, "NLopt evaluations",
              "NLopt's own limit on function evaluations (each one is a physics solve with "
              "sensitivities). The engine's limit and tolerance apply as well, whichever stops first.",
              min=1, max=100000),
        Param("nlopt_report_step", 0.02, "Show a step when the design moved by",
              "NLopt evaluates trial points as well as accepted ones, some of them almost on top of the "
              "last. A point is shown (and counted as an iteration) only when some variable moved by at "
              "least this much since the last one shown. It must exceed the engine tolerance: "
              "the engine ends a run when a shown step changes the design by less than that.",
              min=0.0, max=1.0, step=0.005, decimals=3),
        Param("nlopt_ftol_rel", 1e-6, "NLopt tolerance",
              "Stop when the objective changes by less than this fraction between steps (ftol_rel).",
              min=1e-12, max=1e-1, step=1e-6, decimals=10),
    )
    max_constraints = None          # every constraint goes to NLopt
    flat_objective_scale = 10.0     # MMA-type subproblems want objective and constraints of similar size
    reports = "evaluation"          # NLopt has no callback: iterate() is called from the objective
    algorithm = ""                  # name of the constant in the nlopt module

    def configure(self, opt, nlopt):
        """Hook for subclasses: set algorithm-specific options on the nlopt.opt object."""

    def run(self, flat, x0, iterate):
        import nlopt                 # lazy, so the module imports (and is listed) without it

        opt = nlopt.opt(getattr(nlopt, self.algorithm), flat.n)
        opt.set_lower_bounds(np.asarray(flat.lower, dtype=float))
        opt.set_upper_bounds(np.asarray(flat.upper, dtype=float))

        report_step = float(self.settings["nlopt_report_step"])
        last = {"x": np.array(x0, dtype=float)}
        reported = {"x": last["x"].copy()}   # the engine already holds the start design

        def objective(x, grad):
            x = np.array(x, dtype=float)
            value = float(flat.f(x))
            if grad.size:
                grad[:] = flat.df(x)
            last["x"] = x
            # Tell the engine about every new point NLopt visits.  The flat view cached
            # this evaluation, so the engine's own evaluation of it costs nothing.
            if np.max(np.abs(x - reported["x"]), initial=0.0) >= report_step:
                reported["x"] = x
                iterate(x)
            return value

        def constraints(result, x, grad):
            x = np.asarray(x, dtype=float)
            result[:] = flat.g(x)
            if grad.size:
                grad[:] = flat.dg(x)     # shape (m, n): row i is the gradient of constraint i

        opt.set_min_objective(objective)
        opt.add_inequality_mconstraint(constraints, np.full(flat.m, CONSTRAINT_TOLERANCE))
        opt.set_maxeval(int(self.settings["nlopt_maxeval"]))
        opt.set_ftol_rel(float(self.settings["nlopt_ftol_rel"]))
        self.configure(opt, nlopt)

        try:
            x = np.asarray(opt.optimize(np.array(x0, dtype=float)), dtype=float)
            code = opt.last_optimize_result()
            success = code > 0
            message = _result_name(nlopt, code)
        except nlopt.RoundoffLimited:
            # Not a failure of the run: NLopt can make no further progress at the last point.
            x, success, message = last["x"], True, "roundoff limited (no further progress possible)"
        return Verdict(success=success, message=message, x=x, evaluations=int(opt.get_numevals()))


#: NLopt's positive (success) and negative (failure) result codes, by value.
_RESULT_NAMES = {1: "SUCCESS", 2: "STOPVAL_REACHED", 3: "FTOL_REACHED", 4: "XTOL_REACHED",
                 5: "MAXEVAL_REACHED", 6: "MAXTIME_REACHED", -1: "FAILURE", -2: "INVALID_ARGS",
                 -3: "OUT_OF_MEMORY", -4: "ROUNDOFF_LIMITED", -5: "FORCED_STOP"}


def _result_name(nlopt, code):
    """NLopt's name for a result code, e.g. 3 -> 'FTOL_REACHED'."""
    return _RESULT_NAMES.get(code, f"result code {code}")

class _CCSAFamily(NLoptOptimizer):
    """MMA and CCSAQ share one NLopt implementation and one extra tunable: the penalty on the first step."""

    params = NLoptOptimizer.params + (
        Param("nlopt_rho_init", 0.1, "NLopt first-step penalty",
              "Initial value of the penalty rho in the conservative approximation (NLopt rho_init; its "
              "own default is 1). Smaller means a bolder first step. Too large a value makes the first "
              "move tiny, and the engine ends a run whose step changes the design by less than its "
              "tolerance.", min=1e-4, max=10.0, step=0.05, decimals=4),
    )

    def configure(self, opt, nlopt):
        opt.set_param("rho_init", float(self.settings["nlopt_rho_init"]))


class NLoptMMA(_CCSAFamily):
    """NLopt's MMA (Svanberg), with the conservative-approximation safeguard of the 2002 paper."""

    name = "nlopt_mma"
    label = "MMA (NLopt)"
    order = 80
    algorithm = "LD_MMA"


class NLoptCCSAQ(_CCSAFamily):
    """NLopt's CCSA with a quadratic model: MMA's globally convergent relative (Svanberg 2002)."""

    name = "nlopt_ccsaq"
    label = "CCSAQ (NLopt)"
    order = 81
    algorithm = "LD_CCSAQ"


class NLoptSLSQP(NLoptOptimizer):
    """NLopt's SLSQP (Kraft 1988): sequential quadratic programming with a dense quasi-Newton matrix."""

    name = "nlopt_slsqp"
    label = "SLSQP (NLopt)"
    order = 82
    algorithm = "LD_SLSQP"
    flat_objective_scale = 1.0      # as for scipy_slsqp: the tolerance is absolute-ish, keep the objective at order 1


class NLoptAugLag(NLoptOptimizer):
    """NLopt's augmented Lagrangian: the constraints become penalties, L-BFGS solves each bound-constrained subproblem."""

    name = "nlopt_auglag"
    label = "Augmented Lagrangian + L-BFGS (NLopt)"
    order = 83
    algorithm = "AUGLAG"
    params = NLoptOptimizer.params + (
        Param("nlopt_local_maxeval", 50, "L-BFGS evaluations per subproblem",
              "Evaluation limit of each inner L-BFGS solve; the augmented Lagrangian then updates "
              "its multipliers and penalty and starts the next one.", min=1, max=10000),
    )

    def configure(self, opt, nlopt):
        local = nlopt.opt(nlopt.LD_LBFGS, opt.get_dimension())
        local.set_ftol_rel(float(self.settings["nlopt_ftol_rel"]))
        local.set_maxeval(int(self.settings["nlopt_local_maxeval"]))
        opt.set_local_optimizer(local)
