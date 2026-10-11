"""test_adam_pto_beso_hard.py — Adam, proportional topology optimisation and hard-kill BESO.

Each is run on the MBB benchmark (m = 0.4, 200 iterations, engine tolerance 0.01)
and its compliance, measured on the final design, is printed next to OC's and,
for the two binary methods, next to soft-kill BESO's.
"""

import numpy as np

from toporia.checks.common import iterate, small_run
from toporia.engine.loop import initialized_method
from toporia.plugins.methods import method_class


def _run(name, iterations=200, **values):
    run = small_run(method=name, m=0.4, max_iter=iterations, tol=0.01, **values)
    method = initialized_method(run)
    iterate(method, iterations, tol=0.01)
    return method


def _compliance(method):
    return float(method._model.evaluate(method.x, gradients=False).objective)


def _report(capsys, label, values):
    with capsys.disabled():
        print(f"\nMBB compliance ({label}): "
              + ", ".join(f"{k} {v:.1f}" for k, v in values.items())
              + "  (" + ", ".join(f"{k} {v / values['oc'] - 1:+.1%} vs OC"
                                   for k, v in values.items() if k != "oc") + ")")


def test_adam_mbb_compliance_against_oc_and_holds_the_budget(capsys):
    adam, oc = _run("q4+adam"), _run("q4+oc")
    values = {"oc": _compliance(oc), "adam": _compliance(adam)}
    _report(capsys, "final design", values)
    assert values["adam"] <= 1.10 * values["oc"]
    assert adam.get_density().mean() <= 0.5 * 1.01       # a penalty method: check it did hold the budget


def test_adam_without_the_multiplier_leaves_a_steady_violation_not_a_crash():
    method = _run("q4+adam", **{"method.multiplier": 0})
    assert np.all(np.isfinite(method.get_density()))


def test_pto_mbb_compliance_against_oc(capsys):
    pto, oc = _run("q4+pto"), _run("q4+oc")
    values = {"oc": _compliance(oc), "pto": _compliance(pto)}
    _report(capsys, "final design", values)
    assert values["pto"] <= 1.10 * values["oc"]
    assert pto.get_density().mean() <= 0.5 * 1.01


def test_hard_kill_beso_removed_elements_sit_exactly_at_the_void_bound(capsys):
    hard, soft, oc = _run("q4+beso_hard"), _run("q4+beso"), _run("q4+oc")
    values = {"oc": _compliance(oc), "beso": _compliance(soft), "beso_hard": _compliance(hard)}
    _report(capsys, "final design", values)
    x, lower = hard.x, hard.problem.lower_bound
    assert np.all((np.abs(x - lower) < 1e-12) | (np.abs(x - 1.0) < 1e-12)), "not strictly void or solid"
    assert np.any(x == lower) and np.any(x == 1.0)
    soft_void = soft.x[soft.x < 0.5]
    assert np.allclose(soft_void, 0.001)                  # the contrast: soft kill leaves 0.001 behind
    assert values["beso_hard"] <= 1.10 * values["oc"]
    assert hard.get_density().mean() <= 0.5 * 1.01


def test_new_updaters_are_registered():
    for name in ("adam", "pto", "beso_hard"):
        cls = method_class(f"q4+{name}")
        assert cls.updater.name == name
    assert method_class("q4+beso_hard").updater.needs_element_densities
    assert method_class("q4+pto").updater.needs_element_densities
    assert "void_density" not in {p.name for p in method_class("q4+beso_hard").updater.params}
