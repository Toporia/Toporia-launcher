# checks/filter.py — is a filter sound?
#
# Output shape and range, its adjoint against finite differences (unless it
# declares exact_adjoint = False), and a short run behind the density filter.


import numpy as np

from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import RectangularProblem

from .common import (
    check_declaration,
    gradient_check,
    iterate,
    registered,
    small_run,
)
from .report import Report

# ── Filter ────────────────────────────────────────────────────────────────────

def check_filter(cls):
    """Check a Filter: output shape and range, its adjoint, and a short run behind it."""
    from toporia.plugins.filters import FILTERS
    report = Report(f"filter {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    if not report.ok:
        return report
    run = small_run(m=0.4)
    problem = RectangularProblem(run.scenario, run.solver.m)
    filt = cls(**resolve_params(cls.name, cls.params, {}))
    with report.step("forward: shape and range"):
        filt.setup(problem, run.solver)
        if hasattr(filt, "step"):
            filt.step(10_000)        # end of any continuation: the sharpest, least linear state
        rng = np.random.default_rng(0)
        x = rng.uniform(0.05, 0.95, (problem.nely, problem.nelx))
        y = filt.forward(x)
        assert np.shape(y) == x.shape, f"forward returned shape {np.shape(y)}"
        assert np.all(np.isfinite(y)) and y.min() >= -1e-9 and y.max() <= 1 + 1e-9, "forward left [0, 1]"
    if not report.ok:
        return report

    if getattr(cls, "exact_adjoint", True):
        weights = rng.normal(size=x.shape)
        gradient_check(lambda z: float(np.sum(weights * filt.forward(z))), filt.backward(x, weights),
                        x, np.ones_like(x, dtype=bool), report, "adjoint (backward) vs finite differences")
    else:
        report.add("adjoint (backward) vs finite differences", None,
                   "declared exact_adjoint = False (a heuristic, not a derivative)")

    with registered(FILTERS, cls):
        with report.step("short run behind the density filter, with q4+oc"):
            from toporia.engine.loop import initialized_method
            run = small_run(method="q4+oc", m=0.4, max_iter=4, tol=0.0,
                       filter_specs=[{"type": "density"}, {"type": cls.name}])
            method = initialized_method(run)
            iterate(method, 4)
            assert np.all(np.isfinite(method.get_density())), "the design has non-finite entries"
    return report
