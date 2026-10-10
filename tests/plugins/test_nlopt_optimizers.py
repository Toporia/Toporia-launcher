"""test_nlopt_optimizers.py — the NLopt updaters conform, enforce constraints and stop cleanly.

Skipped when the optional dependency is missing: pip install nlopt
"""

import pytest

pytest.importorskip("nlopt")

from toporia.checks import conformance  # noqa: E402
from toporia.checks.common import small_run  # noqa: E402
from toporia.engine.loop import initialized_method  # noqa: E402
from toporia.plugins.updaters import UPDATERS  # noqa: E402

NAMES = ["nlopt_mma", "nlopt_ccsaq", "nlopt_slsqp", "nlopt_auglag"]


@pytest.mark.parametrize("name", NAMES)
def test_conforms(name):
    conformance(f"updater:{name}").assert_ok()


@pytest.mark.parametrize("name", NAMES)
def test_is_registered_with_its_dependency_declared(name):
    assert name in UPDATERS.names()
    assert UPDATERS.get(name).dependencies == ("nlopt",)


def test_stopping_early_unwinds_the_library_thread_and_reports_no_verdict():
    run = small_run(method="q4+nlopt_mma", m=0.4, max_iter=50, tol=0.0)
    method = initialized_method(run)
    try:
        for iteration in range(1, 4):
            method.step(iteration)
    finally:
        method.close()
    report = method._updater.report()
    assert report["finished"] is False
    assert not method._updater._thread.is_alive()


def test_the_library_can_finish_by_itself_and_its_verdict_is_recorded():
    run = small_run(method="q4+nlopt_slsqp", m=0.4, max_iter=300, tol=0.0)
    method = initialized_method(run)
    try:
        for iteration in range(1, 301):
            method.step(iteration)
            if method.is_converged():
                break
    finally:
        method.close()
    report = method._updater.report()
    assert report["finished"] is True and report["success"] is True
    assert report["evaluations"] > 0
