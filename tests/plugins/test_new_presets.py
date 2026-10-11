"""test_new_presets.py — the L-bracket and the robust MBB presets (plugins/problems/).

The L-bracket must mesh with its corner removed and run; the robust preset must
evaluate three designs per iteration and drive beta by its schedule.
"""

import numpy as np

from toporia.engine.loop import initialized_method, run_single_with_store
from toporia.plugins.problems import get_run, problem_names


def test_presets_are_listed():
    assert {"L-bracket", "MBB Beam (Robust)"} <= set(problem_names())


def test_l_bracket_meshes_without_its_corner_and_runs():
    run = get_run("L-bracket").updated(m=0.3, max_iter=4, tol=0.0, save_every=0)
    store, _ = run_single_with_store(run)
    assert len(store.responses["objective"]) == 4
    assert np.all(np.isfinite(store.responses["objective"]))


def test_robust_preset_evaluates_three_designs_per_iteration():
    run = get_run("MBB Beam (Robust)").updated(m=0.3, max_iter=3, tol=0.0, save_every=0)
    method = initialized_method(run)
    method.step(1)
    assert method.get_responses()["solves"] == 3
    store, _ = run_single_with_store(run)
    assert store.responses["solves"][-1] == 9          # three designs, three iterations
    assert store.responses["filters[1].beta"][0] == 1.0  # the geometric schedule starts beta at 1
