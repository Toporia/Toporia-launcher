# checks/updater.py — is an updater sound, and does it optimise?
#
# A short run on the Drone Arm (holes and solid rings) must stay finite and
# inside the bounds and leave no thread behind; then the MBB benchmark, under
# the engine's stopping rule, must end within the volume budget and within
# `tolerance` of optimality criteria's compliance.


import numpy as np

from toporia.framework.parts.composition import ComposedMethod
from toporia.framework.parts.method import OBJECTIVE
from toporia.framework.problem.mesh import RectangularProblem

from .common import (
    BENCHMARK,
    WITH_HOLES,
    check_declaration,
    iterate,
    no_threads_left,
    optimiser_threads,
    registered,
    small_run,
)
from .report import Report, Skip

# ── Updater ───────────────────────────────────────────────────────────────────

_reference = {}


def _oc_compliance(m, max_iter):
    """Optimality criteria's compliance on the benchmark: what an updater is measured against."""
    key = (m, max_iter)
    if key not in _reference:
        from toporia.plugins.methods import method_class
        run = small_run(method="q4+oc", m=m, max_iter=max_iter, tol=0.01)
        method = method_class("q4+oc")()
        method.initialize(RectangularProblem(run.scenario, run.solver.m), run.solver)
        iterate(method, max_iter, tol=0.01)
        _reference[key] = float(method._model.evaluate(method.x, gradients=False).objective)
    return _reference[key]


def check_updater(cls, model="q4", benchmark=True, tolerance=0.10, m=0.4, max_iter=200):
    """Check an Updater: a short run on a problem with holes, and the MBB benchmark against OC."""
    from toporia.engine.loop import initialized_method
    from toporia.plugins.methods import method_class
    from toporia.plugins.updaters import UPDATERS

    report = Report(f"updater {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    if not report.ok:
        return report
    before = optimiser_threads()
    with registered(UPDATERS, cls):
        method_cls = method_class(f"{model}+{cls.name}")
        with report.step(f"short run on the {WITH_HOLES} with {model}") as check:
            run = small_run(WITH_HOLES, method=method_cls.name, m=0.3, max_iter=4, tol=0.0, volfrac=0.4)
            method = initialized_method(run)
            try:
                iterate(method, 4)
            finally:
                method.close()
            density = method.get_density()
            lower, upper = method.problem.lower_bound, method.problem.upper_bound
            assert np.all(np.isfinite(density)), "the design has non-finite entries"
            x = method.x
            assert np.all(x >= lower - 1e-9) and np.all(x <= upper + 1e-9), "a design variable left its bounds"
            assert np.isfinite(method.get_responses()[OBJECTIVE]), "the objective is not finite"
            check.detail = f"{method.get_responses().get('solves', '?')} solves in 4 iterations, bounds respected"
        no_threads_left(report, before)

        with report.step(f"benchmark: {BENCHMARK}, compliance within {tolerance:.0%} of OC") as check:
            if not benchmark:
                raise Skip("not requested")
            if "compliance" not in method_cls.capabilities.objectives:
                raise Skip("cannot minimise compliance")
            run = small_run(method=method_cls.name, m=m, max_iter=max_iter, tol=0.01)
            method = initialized_method(run)
            try:
                iterate(method, max_iter, tol=0.01)
                # One more evaluation, so the objective belongs to the final design.
                final = method._model.evaluate(method.x, gradients=False) \
                    if isinstance(method, ComposedMethod) else None
            finally:
                method.close()
            compliance = final.objective if final is not None else method.get_responses()[OBJECTIVE]
            volume = float(method.get_density().mean())
            reference = _oc_compliance(m, max_iter)
            assert volume <= run.scenario.volfrac * 1.01, f"volume {volume:.3f} exceeds the budget"
            ratio = compliance / reference
            assert ratio <= 1 + tolerance, f"compliance {compliance:.4g} is {ratio - 1:.1%} above OC's {reference:.4g}"
            check.detail = (f"compliance {compliance:.4g} vs OC {reference:.4g} ({ratio - 1:+.1%}), "
                            f"volume {volume:.3f}")
        no_threads_left(report, before)
    return report
