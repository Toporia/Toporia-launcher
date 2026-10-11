"""test_tobs.py — the TOBS updater (sequential integer linear programming).

TOBS keeps every element void or solid, moves the volume toward the budget by
at most ε per iteration, and flips at most a fraction β of the elements per
iteration.  These tests pin those three properties on the MBB beam and report
its compliance next to OC's and BESO's on the thresholded (binary) design.
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


def test_tobs_design_is_binary_and_reaches_the_volume_target():
    method = _run("q4+tobs")
    x = method.x
    lower = method.problem.lower_bound
    interior = (x > lower + 1e-9) & (x < 1.0 - 1e-9)
    assert not np.any(interior), f"{int(np.sum(interior))} elements are neither void nor solid"
    volfrac = method.get_density().mean()
    assert volfrac <= 0.5 * 1.01
    assert volfrac >= 0.5 * 0.97          # the budget is used, not undershot


def test_tobs_flips_no_more_than_beta_of_the_elements_per_iteration():
    # ε is lowered with β: the cap is never taken below ε (see tobs.py).
    run = small_run(method="q4+tobs", m=0.4, max_iter=12, tol=0.0,
                    **{"method.beta": 0.02, "method.epsilon": 0.01})
    method = initialized_method(run)
    previous = None
    for iteration in range(1, 13):
        method.step(iteration)
        solid = method.x > 0.5
        if previous is not None:
            assert np.sum(solid != previous) <= np.ceil(0.02 * solid.size)
        previous = solid


def test_tobs_mbb_compliance_against_oc_and_beso(capsys):
    tobs, oc, beso = _run("q4+tobs"), _run("q4+oc"), _run("q4+beso")
    values = {name: _compliance(m) for name, m in (("tobs", tobs), ("oc", oc), ("beso", beso))}
    with capsys.disabled():
        print("\nMBB compliance (final design): "
              + ", ".join(f"{k} {v:.1f}" for k, v in values.items())
              + f"  (TOBS {values['tobs'] / values['oc'] - 1:+.1%} vs OC, "
              f"{values['tobs'] / values['beso'] - 1:+.1%} vs BESO)")
    assert values["tobs"] <= 1.10 * values["oc"]
    assert values["tobs"] <= 1.10 * values["beso"]


def test_tobs_is_registered_and_needs_element_densities():
    cls = method_class("q4+tobs")
    assert cls.updater.needs_element_densities
    assert {p.name for p in cls.updater.params} >= {"epsilon", "beta", "average"}
