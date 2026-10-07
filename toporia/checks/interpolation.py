# checks/interpolation.py — is a material law sound?
#
# E(0) = Emin and E(1) = E0 (void is void, solid is solid); E increases with
# density; slope() is the derivative of stiffness() (central finite
# differences); and a short run of q4+oc with this law stays finite.

import numpy as np

from toporia.framework.params import resolve_params

from .common import check_declaration, gradient_check, iterate, registered, small_run
from .report import Report

#: The material the law is checked with: unit stiffness, the usual void stiffness.
E0, EMIN = 1.0, 1e-9


def check_interpolation(cls):
    """Check an Interpolation: its end points, monotonicity, slope, and a short run."""
    from toporia.plugins.interpolations import INTERPOLATIONS
    report = Report(f"interpolation {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    if not report.ok:
        return report
    law = cls(**resolve_params(cls.name, cls.params, {}))

    with report.step("void is void, solid is solid: E(0) = Emin, E(1) = E0") as check:
        ends = law.stiffness(np.array([0.0, 1.0]), E0, EMIN)
        assert np.isclose(ends[0], EMIN, rtol=1e-6, atol=1e-15), f"E(0) = {ends[0]:.6g}, expected {EMIN:g}"
        assert np.isclose(ends[1], E0, rtol=1e-9), f"E(1) = {ends[1]:.6g}, expected {E0:g}"
        middle = float(law.stiffness(np.array([0.5]), E0, EMIN)[0])
        check.detail = f"E(0.5) = {middle:.3g} E0" + ("  (penalises grey)" if middle < 0.5 else "")

    with report.step("stiffness increases with density"):
        grid = np.linspace(0.0, 1.0, 201)
        values = law.stiffness(grid, E0, EMIN)
        assert np.all(np.isfinite(values)), "stiffness is not finite somewhere in [0, 1]"
        assert np.all(np.diff(values) >= -1e-15), "stiffness decreases somewhere in [0, 1]"

    density = np.random.default_rng(0).uniform(0.05, 0.95, (8, 12))
    gradient_check(lambda d: float(np.sum(law.stiffness(d, E0, EMIN))), law.slope(density, E0, EMIN),
                   density, np.ones_like(density, dtype=bool), report, "slope vs finite differences")

    with registered(INTERPOLATIONS, cls):
        with report.step("short run with q4+oc"):
            from toporia.engine.loop import initialized_method
            run = small_run(method="q4+oc", m=0.4, max_iter=4, tol=0.0, interpolation={"type": cls.name})
            method = initialized_method(run)
            iterate(method, 4)
            assert np.all(np.isfinite(method.get_density())), "the design has non-finite entries"
    return report
