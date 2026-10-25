# plugins/updaters/scipy_minimize.py — SciPy's trust-constr, wrapped like scipy_slsqp.py.
#
# Same pattern as scipy_slsqp.py (the worked example in docs/writing-plugins.md): SciPy runs its own
# loop, ExternalOptimizer (framework/optimisers/external_loop.py) runs that loop in a background
# thread on the flat view (framework/optimisers/flat_view.py), and the class below only calls
# scipy.optimize.minimize the way SciPy's documentation says to.
#
#     Toporia                        this adapter                    SciPy
#     -------                        ------------                    -----
#     flat.x0, lower, upper   ──>    x0, bounds                 ──>  minimize(method="trust-constr")
#     flat.f, flat.df         ──>    fun, jac                   ──>
#     flat.g, flat.dg         ──>    NonlinearConstraint(-inf,0)──>  (Toporia's g <= 0 form)
#     iterate                 <──    callback                   <──  once per iteration
#     Verdict                 <──    result.success, .message, .nit, .nfev
#
# trust-constr is a trust-region SQP / interior-point method with exact gradients and a
# quasi-Newton Hessian.  A different algorithm family from SLSQP; dense (n x n) like it, so
# coarse meshes only.  Its callback is callback(xk, state) (SciPy 1.17, state an
# OptimizeResult), so _design() accepts every callback form SciPy uses.
#
# Gradient-free COBYQA and COBYLA were tried with the same adapter and are NOT registered: on the
# MBB benchmark (192 variables) both end about 50 % above OC's compliance after 200 engine
# iterations (COBYQA: ~125 000 solves, 6 min), so they cannot meet the conformance benchmark.
#
# Reference
# ---------
# A. R. Conn, N. I. M. Gould, Ph. L. Toint, "Trust-Region Methods", SIAM 2000;
# https://docs.scipy.org/doc/scipy/reference/optimize.minimize-trustconstr.html

import numpy as np
from scipy.optimize import BFGS, SR1, Bounds, NonlinearConstraint, minimize

from toporia.framework.optimisers.external_loop import ExternalOptimizer, Verdict
from toporia.framework.params import Param


def _design(*args):
    """The design from whatever a SciPy callback passes: (xk), (xk, state) or an OptimizeResult."""
    first = args[0]
    return np.asarray(getattr(first, "x", first), dtype=float)


def _moves_only(iterate, x0):
    """Wrap iterate so a callback that repeats the previous design (or x0) is not reported.

    trust-constr calls back after a rejected trust-region step too, with the old x; the engine
    would read that as "design change 0" and stop at once.  Why here: it is SciPy-specific.
    """
    last = [np.array(x0, dtype=float)]

    def report(*args):
        x = _design(*args)
        if np.array_equal(x, last[0]):
            return
        last[:] = [x]
        iterate(x)
    return report


def _verdict(result):
    """A SciPy OptimizeResult as a Verdict; derivative-free methods have no .nit."""
    return Verdict(success=bool(result.success), message=str(result.message),
                   x=np.asarray(result.x, dtype=float),
                   iterations=int(getattr(result, "nit", 0)) or None,
                   evaluations=int(getattr(result, "nfev", 0)) or None)


class ScipyTrustConstr(ExternalOptimizer):
    """SciPy's trust-constr: trust-region SQP / interior point, any number of constraints."""

    name = "scipy_trust_constr"
    reference = (
        "SciPy's trust-constr (scipy.optimize.minimize); A. R. Conn, N. I. M. Gould and P. L. "
        'Toint, Trust-Region Methods, SIAM 2000.'
        ' Papers: https://doi.org/10.1137/1.9780898719857'
    )
    label = "trust-constr (SciPy)"
    order = 71
    params = (
        Param("trust_constr_maxiter", 200, "trust-constr iterations",
              "SciPy's own iteration limit. The engine's limit and tolerance apply as well, "
              "whichever stops first.", min=1, max=10000),
        Param("trust_constr_gtol", 1e-6, "trust-constr tolerance",
              "SciPy's gtol: stop when the optimality (KKT) residual is below this. The "
              "objective is scaled to start at 100.", min=1e-12, max=1e-1, step=1e-6, decimals=10),
        Param("trust_constr_radius", 0.5, "initial trust radius",
              "Starting trust-region radius in the solver's scaled coordinates. "
              "Smaller is steadier, but a tiny first step can meet the design-change "
              "tolerance before the design has improved.", min=1e-4, max=10.0, step=0.01, decimals=4),
        Param("trust_constr_hessian", "sr1", "Hessian approximation",
              "How trust-constr models curvature from gradient differences. SR1 follows the "
              "negative curvature of compliance under SIMP and converged far faster here than "
              "BFGS (which needs a positive definite model).",
              choices=(("sr1", "SR1"), ("bfgs", "BFGS"))),
    )
    max_constraints = None          # every constraint goes to trust-constr
    # Measured on the MBB benchmark: with the objective starting at 1, trust-constr's barrier
    # term dominates and it crawls (96 % above OC after 200 iterations); starting at 100 it
    # reaches OC's compliance in about 50.  Hence 100, not SLSQP's 1.
    flat_objective_scale = 100.0
    reports = "iteration"           # SciPy calls back once per iteration

    # With feasible bounds, SciPy scales the trust region by the bound slacks.
    # At radius 0.1 the first MBB step is only 0.0054, below Toporia's 0.01
    # stopping tolerance. Radius 0.5 starts with a meaningful step and reaches
    # compliance 278.5 versus OC's 274.5 under the unchanged stopping rule.

    def run(self, flat, x0, iterate):
        # NonlinearConstraint takes lb <= g(x) <= ub; Toporia's g <= 0 is (-inf, 0].
        constraint = NonlinearConstraint(flat.g, -np.inf, 0.0, jac=flat.dg)
        result = minimize(
            flat.f, x0, jac=flat.df, method="trust-constr",
            hess=SR1() if self.settings["trust_constr_hessian"] == "sr1" else BFGS(),
            # Physical densities and geometry parameters must remain in their
            # box during trial solves as well as at the final optimum.
            bounds=Bounds(flat.lower, flat.upper, keep_feasible=True), constraints=[constraint],
            callback=_moves_only(iterate, x0),
            options={"maxiter": self.settings["trust_constr_maxiter"],
                     "gtol": self.settings["trust_constr_gtol"],
                     "initial_tr_radius": self.settings["trust_constr_radius"],
                     # A small starting barrier keeps the iterates near the volume limit
                     # instead of well inside it, where compliance is needlessly high.
                     "initial_barrier_parameter": 1e-4, "initial_constr_penalty": 10.0},
        )
        return _verdict(result)

