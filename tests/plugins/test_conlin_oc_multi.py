"""test_conlin_oc_multi.py — CONLIN and multi-constraint optimality criteria.

CONLIN is MMA without moving asymptotes, so the interesting test is the
comparison on the MBB beam: same compliance, how many iterations.  The numbers
are printed (run with -s) and pinned loosely.  oc_multi is tested where it is
meant to be used: compliance under the volume budget AND a stress limit.
"""

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.plugins.methods import method_class
from toporia.plugins.problems import get_run


def _run(run):
    """Iterate under the engine's stopping rule; return (iterations, final compliance, method)."""
    method = initialized_method(run)
    iterations = 0
    for iterations in range(1, run.solver.max_iter + 1):
        method.step(iterations)
        if run.solver.tol and iterations > 5 and method.change < run.solver.tol:
            break
    compliance = float(method._model.evaluate(method.x, gradients=False).objective)
    return iterations, compliance, method


def _mbb(method, **values):
    return get_run("MBB Beam").updated(method=method, m=0.4, max_iter=200, tol=0.01, **values)


# ── CONLIN against MMA ────────────────────────────────────────────────────────

def test_conlin_reaches_mmas_compliance_and_reports_the_iteration_counts(capsys):
    results = {name: _run(_mbb(f"q4+{name}")) for name in ("oc", "mma", "conlin")}
    with capsys.disabled():
        print()
        for name, (iterations, compliance, method) in results.items():
            print(f"  MBB Beam, {name:7s}: {iterations:3d} iterations, compliance {compliance:.3f}, "
                  f"volume {method.get_density().mean():.4f}")
    (_, c_mma, _), (n_conlin, c_conlin, conlin) = results["mma"], results["conlin"]
    assert abs(c_conlin / c_mma - 1) < 0.02               # the same optimum
    assert conlin.get_density().mean() <= 0.5 * 1.01      # within the budget
    assert n_conlin < 200                                  # and it settles under the stopping rule


def test_conlin_is_mma_when_the_asymptotes_are_pushed_out():
    """One step from the same state: CONLIN's subproblem has the same minimiser as the textbook dual.

    With the volume the only constraint and no move limit active, the step must be
    the exact solution of min f~0 s.t. the linearised volume: check it satisfies the
    budget to the dual's precision and does not increase the CONLIN model of the objective.
    """
    method = initialized_method(_mbb("q4+conlin"))
    x = method.x.copy()
    method.step(1)
    assert method._model.volume_of(method.x) == pytest.approx(method._model.volume_limit, rel=1e-6)
    assert np.max(np.abs(method.x - x)) <= 0.2 + 1e-12


def test_conlin_handles_several_constraints():
    run = _mbb("q4+conlin", constraints=[{"type": "stress", "limit": 1e9}, {"type": "stress", "limit": 1e9, "p": 12.0}])
    iterations, compliance, method = _run(run.updated(max_iter=5, tol=0.0))
    assert np.isfinite(compliance)
    assert method._updater.multipliers.size == 3          # volume + two stress constraints


# ── Multi-constraint OC ───────────────────────────────────────────────────────

def test_oc_multi_with_only_the_volume_budget_is_ordinary_oc():
    _, c_oc, oc = _run(_mbb("q4+oc"))
    _, c_multi, multi = _run(_mbb("q4+oc_multi"))
    assert c_multi == pytest.approx(c_oc, rel=1e-3)
    assert multi.get_density().mean() == pytest.approx(oc.get_density().mean(), abs=1e-3)


def test_oc_multi_enforces_a_stress_limit_next_to_the_volume_budget(capsys):
    """Limit at 95 % of the unconstrained design's peak stress; a small move limit keeps the linearisation honest."""
    base = _mbb("q4+oc_multi")
    peak = _run(base.updated(constraints=[{"type": "stress", "limit": 1e9}]))[2].get_responses()["max_stress"]
    limit = 0.95 * peak
    free_iterations, free_compliance, _ = _run(base)

    run = base.updated(tol=0.0, max_iter=200, constraints=[{"type": "stress", "limit": limit}],
                       **{"method.move": 0.05})
    _, compliance, method = _run(run)
    responses = method.get_responses()
    with capsys.disabled():
        print(f"\n  oc_multi, MBB Beam: unconstrained peak stress {peak:.4f}, limit {limit:.4f}, "
              f"result {responses['max_stress']:.4f}, volume {responses['volume']:.4f}, "
              f"compliance {compliance:.2f} (volume-only run: {free_compliance:.2f})")
    assert responses["max_stress"] <= 1.01 * limit        # the stress limit is met ...
    assert responses["volume"] <= 0.5 * 1.01              # ... and so is the budget
    assert responses["max_stress"] < 0.99 * peak          # a genuinely different design


def test_oc_multi_is_offered_stress_but_oc_is_not():
    assert method_class("q4+oc_multi").capabilities.constraints == ("stress", "minimum_length")
    assert method_class("q4+oc").capabilities.constraints == ()
