"""Composition checks exercise domain bounds and real solves, not just graph drawing."""

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from toporia.engine.workflow import combine, execute_workflow, restrict_problem
from toporia.framework.problem.run import Run
from toporia.framework.problem.scenario import Scenario
from toporia.framework.problem.solver import Solver
from toporia.framework.problem.workflow import optimization, stage_settings, validate_workflow


def basic_run():
    return Run(scenario=Scenario(Lx=8, Ly=4, volfrac=.5),
               solver=Solver(method="q4+oc", max_iter=5, filter_specs=[{"type": "density", "rmin": 1.2}]))


def test_boolean_operations_preserve_shape_and_difference_order():
    a = np.array([[1., .2], [.8, 0.]])
    b = np.array([[.1, 1.], [.6, 0.]])
    np.testing.assert_array_equal(combine([a, b], "union"), [[1, 1], [1, 0]])
    np.testing.assert_array_equal(combine([a, b], "intersection"), [[0, 0], [1, 0]])
    np.testing.assert_array_equal(combine([a, b], "difference"), [[1, 0], [0, 0]])
    with pytest.raises(ValueError, match="same mesh"):
        combine([a, b[:1]], "union")


def test_restriction_changes_bounds_and_budget_without_mutating_original():
    run = basic_run()
    allowed = np.ones((4, 8), dtype=bool)
    allowed[:2, 4:] = False
    restricted, problem = restrict_problem(run, allowed)
    assert restricted.scenario.volfrac == pytest.approx(.5 * allowed.mean())
    assert run.scenario.volfrac == .5
    assert not problem.upper_bound[~allowed].any()
    with pytest.raises(ValueError, match="empty"):
        restrict_problem(run, np.zeros_like(allowed))


def test_sequential_real_solve_cannot_reintroduce_previous_void(tmp_path):
    run = basic_run().with_output_dir(tmp_path)
    first, second = optimization("First"), optimization("Second")
    first["settings"] = stage_settings(run)
    second["settings"] = stage_settings(run)
    tree = {"id": "sequence", "name": "Sequence", "kind": "sequential", "children": [first, second]}
    result = execute_workflow(run, tree)
    previous = np.load(tmp_path / first["id"] / "design.npy")
    allowed = np.load(tmp_path / second["id"] / "allowed_domain.npy")
    np.testing.assert_array_equal(allowed, previous >= .5)
    assert allowed.any() and not allowed.all()
    current = np.load(result["path"])
    assert not current[~allowed].any()
    assert (tmp_path / "run.json").exists()


def test_nested_parallel_then_sequential_has_explicit_completed_result(tmp_path):
    run = basic_run().with_output_dir(tmp_path)
    a, b, c = optimization("A"), optimization("B"), optimization("C")
    for node in (a, b, c):
        node["settings"] = stage_settings(run)
    b["settings"] = stage_settings(replace(run, scenario=replace(run.scenario, volfrac=.65)))
    parallel = {"id": "branches", "name": "Branches", "kind": "parallel", "operation": "union", "children": [a, b]}
    tree = {"id": "sequence", "name": "Sequence", "kind": "sequential", "children": [parallel, c]}
    calls = []
    result = execute_workflow(run, tree, on_stage=lambda node, _: calls.append(node["name"]))
    assert calls == ["A", "B", "C"]
    expected = combine([np.load(tmp_path / n["id"] / "design.npy") for n in (a, b)], "union") >= .5
    np.testing.assert_array_equal(np.load(tmp_path / c["id"] / "allowed_domain.npy"), expected)
    assert np.isfinite(np.load(result["path"])).all()


def test_workflow_validation_refuses_duplicate_ids_paths_and_unknown_execution():
    leaf = optimization()
    tree = {"id": "root", "kind": "parallel", "name": "Root", "children": [leaf, deepcopy(leaf)]}
    with pytest.raises(ValueError, match="unique"):
        validate_workflow(tree)
    leaf["id"] = "../elsewhere"
    with pytest.raises(ValueError, match="safe"):
        validate_workflow(leaf)
    leaf = optimization()
    leaf["kind"] = "coupled"
    with pytest.raises(ValueError, match="Unsupported"):
        validate_workflow(leaf)
