"""test_conformance.py — every plugin passes the conformance test, and the test has teeth.

toporia.checks.conformance is what a plugin author runs on a new class.  Here
it runs on every registered plugin, and on deliberately broken ones, to show it
catches what it claims to catch: a design that leaves its bounds, a wrong
adjoint, a wrong gradient, a poor optimiser.
"""

import pytest

from toporia.checks import Report, all_plugins, conformance
from toporia.framework.parts.updater import Updater
from toporia.plugins.filters.density import DensityFilter
from toporia.plugins.models.q4 import Q4Model
from toporia.plugins.updaters.oc import OCUpdater


@pytest.mark.parametrize("plugin", all_plugins())
def test_every_registered_plugin_conforms(plugin):
    conformance(plugin).assert_ok()


def _failed(report):
    return [check.name for check in report.checks if check.passed is False]


# ── The checks catch what they claim to ───────────────────────────────────────

class _LeavesItsBounds(OCUpdater):
    name, label = "leaves_bounds", "Leaves its bounds"

    def update(self, x, evaluation, completed):
        return super().update(x, evaluation, completed) + 0.5


class _Stalls(Updater):
    """Never moves the design: feasible, but far from optimal."""
    name, label = "stalls", "Stalls"

    def initialize(self, model, settings):
        pass

    def update(self, x, evaluation, completed):
        return x


class _WrongAdjoint(DensityFilter):
    name, label = "wrong_adjoint", "Wrong adjoint"

    def backward(self, x_in, sensitivity):
        return 1.1 * super().backward(x_in, sensitivity)


class _WrongGradient(Q4Model):
    name, label = "wrong_gradient", "Wrong gradient"

    def evaluate(self, x, gradients=True):
        evaluation = super().evaluate(x, gradients)
        if gradients:
            object.__setattr__(evaluation, "objective_gradient", evaluation.objective_gradient * 0.9)
        return evaluation


def test_an_updater_that_leaves_its_bounds_is_caught():
    report = conformance(_LeavesItsBounds, benchmark=False)
    assert not report.ok
    assert any("short run" in name for name in _failed(report))


def test_an_updater_that_does_not_optimise_fails_the_benchmark():
    report = conformance(_Stalls)
    assert any(name.startswith("benchmark") for name in _failed(report))
    assert "above OC" in str(report)


def test_a_wrong_adjoint_is_caught():
    report = conformance(_WrongAdjoint)
    assert _failed(report) == ["adjoint (backward) vs finite differences"]


def test_a_wrong_gradient_is_caught_and_located():
    report = conformance(_WrongGradient)
    assert _failed(report) == ["objective gradient vs finite differences"]
    assert "finite difference" in str(report)


def test_a_failed_check_reports_the_exception_and_where_it_happened():
    report = Report("subject")
    with report.step("divides"):
        raise ZeroDivisionError("boom")
    assert not report.ok
    assert "ZeroDivisionError: boom" in report.checks[0].detail and "test_conformance.py" in report.checks[0].detail


def test_a_plugin_can_be_named_or_passed_as_a_class():
    assert conformance("filter:symmetry").ok
    with pytest.raises(ValueError, match="kind:name"):
        conformance("symmetry")
