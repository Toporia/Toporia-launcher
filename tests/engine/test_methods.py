"""test_methods.py — comparing methods on one problem, and benchmarking across problems.

The comparison is what Toporia is for, so it must be fair: every method on
the same scenario, mesh and stopping rule, one referee measuring every
design the same way, and a method that cannot take part named with its
reason instead of stopping the comparison.
"""

import csv

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from toporia.engine.modes.methods import (  # noqa: E402
    COLUMNS,
    benchmark,
    compare_methods,
    grey_level,
    referee_compliance,
)
from toporia.framework.problem.mesh import RectangularProblem  # noqa: E402
from toporia.plugins.models.q4 import Q4Model  # noqa: E402
from toporia.plugins.problems import get_run, problem_names  # noqa: E402

SMALL = {"m": 0.3, "max_iter": 25, "save_every": 0}


def _small(problem="MBB Beam", **values):
    return get_run(problem).updated(**{**SMALL, **values})


def test_every_method_runs_on_the_same_problem_and_lands_in_one_table(tmp_path):
    run = _small().with_output_dir(tmp_path)
    grid, rows = compare_methods(["q4+oc", "q4+mma", "q4+oc"], run)    # a repeat runs once
    assert [row["method"] for row in rows] == ["q4+oc", "q4+mma"]
    assert all(row["status"] == "ran" and row["feasible"] for row in rows)
    assert grid.exists()
    with open(tmp_path / "compare_methods" / "methods.csv", newline="", encoding="utf-8") as file:
        table = list(csv.DictReader(file))
    assert list(table[0]) == list(COLUMNS) and len(table) == 2
    for row in rows:
        assert (tmp_path / "compare_methods" / row["method"] / "run.json").exists()


def test_a_method_that_cannot_take_part_is_listed_with_its_reason(tmp_path):
    run = _small(constraints=[{"type": "stress", "limit": 50.0}], max_iter=3).with_output_dir(tmp_path)
    _, rows = compare_methods(["q4+oc", "q4+pymoto_mma"], run)
    skipped, ran = rows
    assert skipped["status"] == "skipped" and "cannot enforce" in skipped["stop_reason"]
    assert ran["status"] == "ran"


def test_one_methods_settings_do_not_stop_another(tmp_path):
    """The GUI passes the selected method's parameters; a different method must ignore them."""
    run = _small(method_params={"move": 0.1, "mma_tol": 1e-3}).with_output_dir(tmp_path)
    _, rows = compare_methods(["levelset", "q4+mma"], run)
    assert [row["status"] for row in rows] == ["ran", "ran"]


def test_the_referee_measures_a_design_like_the_q4_model_without_a_filter():
    run = _small(filter_specs=[])
    problem = RectangularProblem(run.scenario, run.solver.m)
    model = Q4Model()
    model.initialize(problem, run.solver, {"penal": 3.0})
    design = np.clip(np.random.default_rng(0).uniform(0.1, 1.0, (problem.nely, problem.nelx)),
                     problem.lower_bound, problem.upper_bound)
    assert referee_compliance(run, design) == pytest.approx(model.evaluate(design, gradients=False).objective)


def test_the_grey_level_is_zero_for_black_and_white_and_one_for_uniform_grey():
    assert grey_level(np.array([[0.0, 1.0], [1.0, 0.0]])) == 0.0
    assert grey_level(np.full((3, 3), 0.5)) == pytest.approx(1.0)


def test_the_level_set_is_no_longer_stopped_before_it_reaches_its_volume(tmp_path):
    """Its get_change used to be the compliance's relative change; the engine stopped it at iteration 3.

    The mesh is 30 x 10: on coarser ones the level set's smoothing band (several
    elements wide) covers the whole domain and the method itself does not converge.
    """
    run = _small(m=0.5, max_iter=60).with_output_dir(tmp_path)
    _, (row,) = compare_methods(["levelset"], run)
    assert row["iterations"] == 60                       # not stopped early by the tolerance
    assert row["volume"] < 0.6                           # on its way from 0.9 to the 0.5 budget


def test_a_benchmark_runs_every_method_on_every_problem(tmp_path):
    rows = benchmark(["q4+oc", "q4+simpl"], ["MBB Beam", "Cantilever"], {"m": 0.3, "max_iter": 10},
                     tmp_path)
    assert [(row["problem"], row["method"]) for row in rows] == [
        ("MBB Beam", "q4+oc"), ("MBB Beam", "q4+simpl"), ("Cantilever", "q4+oc"), ("Cantilever", "q4+simpl")]
    assert (tmp_path / "benchmark.csv").exists()
    assert (tmp_path / "MBB_Beam" / "compare_methods" / "methods_grid.png").exists()


def test_the_michell_cantilever_is_a_preset():
    assert "Michell Cantilever" in problem_names()
    run = get_run("Michell Cantilever")
    problem = RectangularProblem(run.scenario, 0.5)
    assert problem.void_elements.any() and problem.passive_elements.any()   # the support ring
