# checks/schedule.py — is a continuation schedule sound?
#
# Its values are finite; it finishes (within 10 000 iterations) and does not
# move once it says it has; and a short run with it driving the sharpness of a
# Heaviside projection stays finite.

import numpy as np

from toporia.framework.params import resolve_params

from .common import check_declaration, registered, small_run
from .report import Report

#: How far a schedule is followed when looking for its end.
HORIZON = 10_000


def check_schedule(cls):
    """Check a Schedule: finite values, a finish it keeps, and a short run."""
    from toporia.plugins.schedules import SCHEDULES
    report = Report(f"schedule {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    if not report.ok:
        return report
    schedule = cls(**resolve_params(cls.name, cls.params, {}))

    with report.step("finite values, a finish, and no change after it") as check:
        values = np.array([schedule.value(c) for c in range(HORIZON)], dtype=float)
        assert np.all(np.isfinite(values)), "value() is not finite somewhere"
        done = next((c for c in range(HORIZON) if schedule.finished(c)), None)
        assert done is not None, f"finished() is still False after {HORIZON} iterations"
        after = values[done:]
        assert np.all(after == after[0]), f"value() still changes after finished() at iteration {done}"
        check.detail = f"{values[0]:g} -> {after[0]:g}, finished after {done} iterations"
    if not report.ok:
        return report

    with registered(SCHEDULES, cls):
        with report.step("short run driving a Heaviside sharpness, with q4+oc") as check:
            if np.min(values) <= 0:
                check.detail = "skipped: its default values are not a valid sharpness"
            else:
                from toporia.engine.loop import initialized_method
                run = small_run(method="q4+oc", m=0.4, max_iter=4, tol=0.0,
                                filter_specs=[{"type": "density"}, {"type": "heaviside"}],
                                schedules=[{"path": "filters[1].beta", "type": cls.name}])
                method = initialized_method(run)
                for iteration in range(1, 5):            # as the engine does: set, then step
                    method.set_parameter("filters[1].beta", schedule.value(iteration - 1))
                    method.step(iteration)
                assert np.all(np.isfinite(method.get_density())), "the design has non-finite entries"
    return report
