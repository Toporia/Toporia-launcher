# plugins/updaters/scipy_slsqp.py — SciPy's SLSQP, the template for wrapping a plugins.
#
# This file is the worked example in docs/writing-plugins.md.  It is the whole
# adapter: SciPy runs its own loop, and ExternalOptimizer (framework/optimisers/external_loop.py)
# runs that loop in a background thread on the flat view (framework/optimisers/flat_view.py), so
# all this file does is call the library the way its documentation says to.
#
#     Toporia                         this adapter                SciPy
#     -------                         ------------                -----
#     flat.x0, lower, upper    ──>    x0, bounds              ──> minimize(method="SLSQP")
#     flat.f, flat.df          ──>    fun, jac                ──>
#     flat.g_geq, flat.dg_geq  ──>    {"type": "ineq", ...}   ──>  (SciPy wants g >= 0)
#     iterate                  <──    callback                <──  once per iteration
#     Verdict                  <──    result.success, .message, .nit, .nfev
#
# SLSQP (sequential least-squares quadratic programming, Kraft 1988) keeps a
# dense quasi-Newton matrix of size n × n, so its cost grows with the square of
# the number of design variables: fine on coarse meshes (a few thousand
# elements), slow beyond.  It takes any number of constraints, so it can
# enforce a stress limit as well as the volume budget.
#
# Reference
# ---------
# D. Kraft, "A software package for sequential quadratic programming",
# DFVLR-FB 88-28, 1988.  scipy.optimize.minimize(method="SLSQP").

import numpy as np
from scipy.optimize import Bounds, minimize

from toporia.framework.optimisers.external_loop import ExternalOptimizer, Verdict
from toporia.framework.params import Param


class ScipySLSQP(ExternalOptimizer):
    """SciPy's SLSQP: sequential quadratic programming with any number of constraints."""

    name = "scipy_slsqp"
    label = "SLSQP (SciPy)"
    order = 70
    params = (
        Param("slsqp_maxiter", 200, "SLSQP iterations",
              "SciPy's own iteration limit. The engine's limit and tolerance apply as well, "
              "whichever stops first.", min=1, max=10000),
        Param("slsqp_ftol", 1e-6, "SLSQP tolerance",
              "SciPy's precision goal on the objective (ftol). The objective is scaled to start at 1.",
              min=1e-12, max=1e-1, step=1e-6, decimals=10),
    )
    max_constraints = None          # every constraint goes to SLSQP
    flat_objective_scale = 1.0      # SLSQP's ftol is absolute, so give it an objective of order 1
    reports = "iteration"           # SciPy calls back once per iteration

    def run(self, flat, x0, iterate):
        result = minimize(
            flat.f, x0, jac=flat.df, method="SLSQP",
            bounds=Bounds(flat.lower, flat.upper),
            constraints=[{"type": "ineq", "fun": flat.g_geq, "jac": flat.dg_geq}],
            callback=iterate,
            options={"maxiter": self.settings["slsqp_maxiter"], "ftol": self.settings["slsqp_ftol"]},
        )
        return Verdict(success=bool(result.success), message=str(result.message),
                       x=np.asarray(result.x, dtype=float),
                       iterations=int(result.nit), evaluations=int(result.nfev))
