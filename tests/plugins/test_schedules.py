"""test_schedules.py — continuation: parameters that change during a run.

A schedule drives any parameter its part allows to change mid-run; the engine
applies it before every iteration, records it, and does not stop on its
tolerance while it is still moving.  A schedule on a parameter that cannot
change is refused before the run.
"""

import json

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single_with_store
from toporia.engine.pipeline import pipeline_parts, pipeline_stages
from toporia.framework.problem.run import apply_param, read_param
from toporia.plugins.catalog import parameter_paths, schedulable_paths
from toporia.plugins.problems import get_run
from toporia.plugins.schedules import SCHEDULES
from toporia.plugins.schedules.geometric import Geometric
from toporia.plugins.schedules.linear import Linear
from toporia.plugins.schedules.steps import Steps

PENAL = {"path": "interpolation.penal", "type": "steps", "start": 1.0, "end": 3.0, "step": 0.5, "every": 5}


def _run(**values):
    return get_run("MBB Beam").updated(**{"m": 0.3, "max_iter": 30, "tol": 0.0, "save_every": 0, **values})


def test_three_kinds_are_registered():
    assert SCHEDULES.names() == ["steps", "geometric", "linear"]


def test_each_kind_reaches_its_end_and_stays_there():
    steps = Steps(start=1, end=3, step=0.5, every=20)
    assert [steps.value(c) for c in (0, 19, 20, 40, 80, 500)] == [1, 1, 1.5, 2, 3, 3]
    assert not steps.finished(79) and steps.finished(80)
    assert Steps(start=3, end=1, step=0.5, every=1).value(10) == 1        # downwards, same positive step

    doubling = Geometric(start=1, end=64, factor=2, every=50)
    assert [doubling.value(c) for c in (0, 50, 100, 300, 1000)] == [1, 2, 4, 64, 64]

    ramp = Linear(start=0, end=1, after=10, over=20)
    assert ramp.value(5) == 0 and ramp.value(20) == pytest.approx(0.5) and ramp.value(30) == 1
    assert ramp.finished(30) and not ramp.finished(29)


def test_the_penalty_follows_its_schedule_and_is_recorded(tmp_path):
    run = _run(schedules=[PENAL]).with_output_dir(tmp_path)
    store, _ = run_single_with_store(run)
    penal = store.responses["interpolation.penal"]
    assert penal[:5] == [1.0] * 5 and penal[5] == 1.5 and penal[-1] == 3.0
    record = json.loads((tmp_path / "run.json").read_text())
    assert record["solver"]["definition"]["schedules"] == [PENAL]
    assert [p["name"] for p in record["parts"] if p["kind"] == "schedule"] == ["steps"]


def test_continuation_changes_the_result():
    plain = initialized_method(_run())
    scheduled = initialized_method(_run(schedules=[PENAL]))
    scheduled.set_parameter("interpolation.penal", 1.0)
    for method in (plain, scheduled):
        method.step(1)
    assert method.get_responses()["objective"] != plain.get_responses()["objective"]


def test_the_engine_does_not_stop_while_a_schedule_is_moving(capsys):
    run = _run(method="q4+oc", tol=0.5, max_iter=40, schedules=[PENAL])   # tol met at once
    store, _ = run_single_with_store(run)
    out = capsys.readouterr().out
    assert "still moving" in out
    assert len(store.objectives) >= 21          # p reaches 3 after 20 completed iterations
    assert store.responses["interpolation.penal"][-1] == 3.0


def test_the_heaviside_doubling_holds_the_stop_too():
    run = _run(method="q4+oc", tol=0.5, max_iter=40,
               filter_specs=[{"type": "density"}, {"type": "heaviside", "beta_max": 8, "beta_interval": 5}])
    store, _ = run_single_with_store(run)
    assert len(store.objectives) >= 15          # beta 1 -> 8 takes three doublings, every 5


def test_a_schedule_on_beta_replaces_the_built_in_doubling():
    run = _run(method="q4+oc", max_iter=12,
               filter_specs=[{"type": "density"}, {"type": "heaviside", "beta_interval": 2}],
               schedules=[{"path": "filters[1].beta", "type": "geometric", "start": 1, "end": 4, "every": 5}])
    method = initialized_method(run)
    heaviside = method._model.pipeline.chain.filters[1]
    for iteration in range(1, 13):
        method.set_parameter("filters[1].beta", Geometric(start=1, end=4, every=5).value(iteration - 1))
        method.step(iteration)
    assert heaviside.beta == 4.0                 # the doubling every 2 would have passed 32


@pytest.mark.parametrize("path, reason", [
    ("filters[0].rmin", "cannot change 'rmin'"),            # built into the filter's weights
    ("interpolation.pnal", "cannot change 'pnal'"),
    ("filters[5].beta", "drives nothing"),
])
def test_a_schedule_that_cannot_work_is_refused_before_the_run(path, reason):
    with pytest.raises(ValueError, match=reason):
        initialized_method(_run(schedules=[{"path": path, "type": "steps"}]))


def test_its_values_can_be_swept_and_its_targets_are_offered():
    run = apply_param(_run(schedules=[PENAL]), "schedules[0].end", 4.0)
    assert read_param(run, "schedules[0].end") == 4.0
    paths = [path for _, path in parameter_paths("q4+oc", schedules=[PENAL])]
    assert {"schedules[0].start", "schedules[0].every"} <= set(paths)
    targets = [path for _, path in schedulable_paths(
        "q4+mma", [{"type": "density"}, {"type": "heaviside"}], interpolation={"type": "simp"},
        representation={"type": "mmc"})]
    assert targets == ["method.move", "representation.edge_width", "interpolation.penal",
                       "filters[1].beta", "filters[1].eta"]


def test_it_is_shown_in_the_pipeline():
    run = _run(schedules=[PENAL])
    assert dict(pipeline_stages(run))["Schedules"] == "interpolation.penal 1 -> 3, +0.5 every 5 iterations"
    assert ("schedule", Steps) in pipeline_parts(run)


def test_mmc_edges_can_be_sharpened_during_the_run():
    run = _run(method="q4+mma", m=0.5, representation={"type": "mmc"}, method_params={"move": 0.02},
               schedules=[{"path": "representation.edge_width", "type": "linear", "start": 3, "end": 1,
                           "over": 10}], max_iter=12)
    store, density = run_single_with_store(run)
    assert store.responses["representation.edge_width"][-1] == 1.0
    assert np.all(np.isfinite(density))
