"""test_external.py — optimisers that run their own loop (core/external.py).

The libraries worth plugging in (SciPy, NLopt, IPOPT) call Toporia, not the
other way round.  These tests use small fake optimisers, written exactly as
such a library would be driven, to pin the hand-over: every design reaches the
engine, the engine's stopping rule and the Stop button still work, the thread
never outlives the run, errors surface where the run was started, and the
optimiser's own verdict lands in run.json.
"""

import json
import threading

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single_with_store
from toporia.framework.optimisers.external_loop import ExternalOptimizer, Verdict
from toporia.plugins.problems import get_run
from toporia.plugins.updaters import UPDATERS


class _Descent(ExternalOptimizer):
    """A projected-gradient loop that, like SciPy, reports through a callback."""

    name = "test_descent"
    label = "Test descent"
    iterations = 6
    record = []

    def run(self, flat, x0, iterate):
        x, evaluations = x0, 0
        for _ in range(self.iterations):
            gradient = flat.df(x)
            evaluations += 1
            x = np.clip(x - 0.05 * np.sign(gradient), flat.lower, flat.upper)
            type(self).record.append(x.copy())
            iterate(x)
        return Verdict(True, "converged (test)", x, iterations=self.iterations, evaluations=evaluations)


class _Failing(_Descent):
    name = "test_failing"

    def run(self, flat, x0, iterate):
        iterate(x0)
        raise FloatingPointError("the library gave up")


class _FinalOnly(_Descent):
    name = "test_final_only"
    reports = "final"

    def run(self, flat, x0, iterate):
        return Verdict(False, "iteration limit reached (test)", np.clip(x0 + 0.1, flat.lower, flat.upper))


@pytest.fixture(autouse=True)
def registered():
    for cls in (_Descent, _Failing, _FinalOnly):
        UPDATERS.register(cls)
    _Descent.record = []
    yield
    for cls in (_Descent, _Failing, _FinalOnly):
        UPDATERS.unregister(cls.name)


def _run(updater, tmp_path=None, **values):
    run = get_run("MBB Beam").updated(method=f"q4+{updater}", m=0.3, tol=0.0, save_every=0, **values)
    return run.with_output_dir(tmp_path) if tmp_path is not None else run


def _optimiser_threads():
    return [t for t in threading.enumerate() if t.name.startswith("toporia-test")]


# ── The hand-over ─────────────────────────────────────────────────────────────

def test_every_design_the_library_reaches_is_handed_to_the_engine():
    method = initialized_method(_run("test_descent", max_iter=4))
    for iteration in range(1, 4):
        method.step(iteration)
        assert np.array_equal(method._updater.flat.reduce(method.x), _Descent.record[-1])
    method.close()
    assert not _optimiser_threads()


def test_designs_the_library_already_evaluated_cost_no_second_solve():
    method = initialized_method(_run("test_descent", max_iter=4))
    for iteration in range(1, 4):
        method.step(iteration)
    method.close()
    # One solve per design: the start, then each handed-over design once
    # (by the engine), which the library then finds in the cache.
    assert method.get_responses()["solves"] == 3


def test_a_library_that_finishes_first_ends_the_run_with_its_verdict(tmp_path):
    store, _ = run_single_with_store(_run("test_descent", tmp_path, max_iter=50))
    assert store.stop_reason == "Test descent finished: converged (test)"
    record = json.loads((tmp_path / "run.json").read_text())["result"]
    # Its six iterations, the step on which it returned, and the step that evaluates its answer.
    assert record["iterations"] == _Descent.iterations + 2
    assert record["optimiser"] == {"optimiser": "Test descent", "finished": True, "success": True,
                                   "message": "converged (test)", "iterations": 6, "evaluations": 6}
    assert not _optimiser_threads()


def test_when_the_engine_stops_first_the_library_is_unwound_and_says_so(tmp_path):
    store, _ = run_single_with_store(_run("test_descent", tmp_path, max_iter=2))
    assert store.stop_reason == "iteration limit (2)"
    assert store.optimiser["finished"] is False
    assert not _optimiser_threads()


def test_the_stop_button_unwinds_the_library():
    class Stop(Exception):
        pass

    def press_stop(density, objectives, iteration):
        if iteration == 2:
            raise Stop()

    with pytest.raises(Stop):
        run_single_with_store(_run("test_descent", max_iter=50), on_iteration=press_stop)
    assert not _optimiser_threads()


def test_an_error_inside_the_library_surfaces_in_the_engine():
    method = initialized_method(_run("test_failing", max_iter=5))
    method.step(1)
    with pytest.raises(FloatingPointError, match="gave up"):
        method.step(2)
    method.close()
    assert not _optimiser_threads()


def test_a_library_that_reports_only_its_answer_is_one_step(tmp_path):
    store, _ = run_single_with_store(_run("test_final_only", tmp_path, max_iter=50))
    assert store.optimiser["success"] is False
    assert "finished: iteration limit reached" in store.stop_reason
    assert len(store.objectives) == 2      # the start, then the answer


# ── Made visible ──────────────────────────────────────────────────────────────

def test_the_pipeline_says_who_owns_the_loop():
    from toporia.engine.pipeline import pipeline_stages
    seen = dict(pipeline_stages(_run("test_descent")))["Optimiser sees"]
    assert "own loop in the background" in seen and "each of its iterations" in seen
    seen = dict(pipeline_stages(_run("test_final_only")))["Optimiser sees"]
    assert "only its final design" in seen
