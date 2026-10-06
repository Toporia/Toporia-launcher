# checks/method.py — is a whole method sound?
#
# A short run of the benchmark; a composed method is checked part by part.


import numpy as np

from toporia.framework.parts.composition import ComposedMethod
from toporia.framework.parts.method import OBJECTIVE

from .common import (
    check_declaration,
    iterate,
    registered,
    small_run,
)
from .model import check_model
from .report import Report
from .updater import check_updater

# ── Whole method ──────────────────────────────────────────────────────────────

def check_method(cls):
    """Check a whole method (one that does not split into a model and an updater)."""
    from toporia.plugins.methods import METHODS
    report = Report(f"method {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    if issubclass(cls, ComposedMethod):
        report.add("parts", True, f"composed of {cls.model.__name__} and {cls.updater.__name__}")
        report.checks.extend(check_model(cls.model).checks)
        report.checks.extend(check_updater(cls.updater).checks)
        return report
    with registered(METHODS, cls):
        with report.step("short run on the benchmark"):
            from toporia.engine.loop import initialized_method
            method = initialized_method(small_run(method=cls.name, m=0.4, max_iter=5, tol=0.0))
            try:
                iterate(method, 5)
            finally:
                method.close()
            density = method.get_density()
            assert np.all(np.isfinite(density)) and density.min() >= -1e-9 and density.max() <= 1 + 1e-9
            assert np.isfinite(method.get_responses()[OBJECTIVE])
    return report
