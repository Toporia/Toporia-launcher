"""test_truss.py — the ground-structure truss and its continuum stage (To do item 3).

The ground structure has no overlapping bars and none through holes, its supports and
loads land on nodes, the bar gradient is exact, a truss is drawn as a density, and the
method runs its truss stage and hands over to the stress check or the stress optimisation,
in 2-D and 3-D.
"""

from dataclasses import replace

import numpy as np
import pytest

from toporia_core.engine.loop import initialized_method
from toporia_core.framework import HoleConfig
from toporia_core.framework.problem.mesh import make_problem
from toporia_library.physics.truss import TrussSolver, bars_to_density, ground_structure
from toporia_library.problems import get_run


def _mbb_problem(**changes):
    run = get_run("MBB Beam")
    return make_problem(replace(run.scenario, **changes), run.solver.m)


def test_the_ground_structure_has_no_overlapping_bars_and_keeps_supports_and_loads():
    problem = _mbb_problem()
    structure = ground_structure(problem, spacing=5.0, reach=2)
    assert structure.nodes.shape[1] == 2 and len(structure.bars) > 100
    directions = {tuple(np.round(d, 6)) for d in structure.directions}
    # Collinear duplicates would share a start node and a direction.
    starts = {(int(i), tuple(np.round(d, 6))) for (i, _), d in zip(structure.bars, structure.directions, strict=True)}
    assert len(starts) == len(structure.bars) and len(directions) >= 8
    # The roller at (60, 0) and the load at (0, 20) are nodes; the load sums to the case's force.
    assert np.any(np.all(np.isclose(structure.nodes, [60.0, 0.0]), axis=1))
    assert structure.forces[0].sum() == pytest.approx(-1.0)
    assert structure.fixed.size > 0


def test_no_bar_crosses_a_hole():
    hole = HoleConfig(cx=30.0, cy=10.0, r_void=5.0, r_passive=5.0)
    problem = _mbb_problem(holes=[hole])
    structure = ground_structure(problem, spacing=5.0, reach=2)
    for i, j in structure.bars:
        a, b = structure.nodes[i], structure.nodes[j]
        t = np.linspace(0.0, 1.0, 50)[:, None]
        distance = np.linalg.norm(a + t * (b - a) - [30.0, 10.0], axis=1)
        assert distance.min() > 4.0


def test_the_bar_gradient_is_exact():
    problem = _mbb_problem()
    structure = ground_structure(problem, spacing=10.0, reach=2)
    solver = TrussSolver(structure, 1.0)
    areas = np.random.default_rng(4).uniform(0.5, 2.0, len(structure.bars))
    _, compliance, gradient = solver.solve(areas)
    for i in np.argsort(-np.abs(gradient))[:5]:
        step = 1e-6 * areas[i]
        up, down = areas.copy(), areas.copy()
        up[i] += step
        down[i] -= step
        fd = (solver.solve(up)[1] - solver.solve(down)[1]) / (2 * step)
        assert gradient[i] == pytest.approx(fd, rel=1e-5)


def test_a_truss_is_drawn_as_a_density():
    problem = _mbb_problem()
    structure = ground_structure(problem, spacing=10.0, reach=1)
    areas = np.zeros(len(structure.bars))
    horizontal = np.flatnonzero(np.isclose(np.abs(structure.directions[:, 0]), 1.0))[0]
    areas[horizontal] = 2.0                     # one bar, 2 mm wide
    density = bars_to_density(problem, structure, areas)
    (i, j) = structure.bars[horizontal]
    y = structure.nodes[i, 1]
    row = int(min(y // problem.dy, problem.nely - 1))
    assert density.shape == problem.shape and density.max() == pytest.approx(1.0)
    assert density[row].sum() > 5 and density.sum() < 40


@pytest.mark.parametrize("stage", ["check", "stress"])
def test_the_truss_stage_hands_over_to_the_continuum(stage):
    run = get_run("MBB Beam").updated(method="truss", tol=0.0)
    run = replace(run, solver=replace(run.solver, filter_specs=[], method_params={
        "stage": stage, "truss_iterations": 8, "spacing": 10.0}))
    method = initialized_method(run)
    for i in range(1, 8):
        method.step(i)
        assert method.continuing()                 # the engine must not stop inside the truss stage
    assert method.get_responses()["truss_compliance"] > 0
    method.step(8)                                 # the last truss iteration hands over
    responses = method.get_responses()
    assert responses["stage"] == 2.0 and responses["converted_peak_stress"] > 0
    assert method.get_density().shape == run_problem_shape(run)
    if stage == "check":
        assert method.is_converged()
    else:
        method.step(9)
        method.step(10)
        assert "peak_stress" in method.get_responses() and not method.continuing()
    network = method.network()
    assert network["nodes"].shape[1] == 2 and len(network["areas"]) == len(network["bars"])


def run_problem_shape(run):
    return make_problem(run.scenario, run.solver.m).shape


def test_a_space_truss_in_3d():
    run = get_run("Cantilever 3D (Truss)").updated(tol=0.0)
    run = replace(run, solver=replace(run.solver, method_params={**run.solver.method_params,
                                                                 "truss_iterations": 5, "spacing": 10.0}))
    method = initialized_method(run)
    for i in range(1, 7):
        method.step(i)
    assert method.network()["nodes"].shape[1] == 3
    assert method.is_converged() and method.get_responses()["converted_compliance"] > 0
    assert method.get_density().ndim == 3


def test_a_run_saves_its_truss_and_sends_it_while_running(tmp_path):
    import json

    from toporia_core.engine.loop import run_single
    run = get_run("MBB Beam (Truss)").updated(max_iter=4, tol=0.0, save_every=0).with_output_dir(tmp_path)
    run = replace(run, solver=replace(run.solver, method_params={**run.solver.method_params, "stage": "none",
                                                                 "spacing": 10.0}))
    sent = []

    def on_iteration(density, objectives, number):
        pass

    on_iteration.on_network = sent.append
    run_single(run, on_iteration)
    saved = json.loads((tmp_path / "network.json").read_text())
    assert len(sent) == 4 and set(saved) == {"nodes", "bars", "areas", "forces"}
    assert len(saved["areas"]) == len(saved["bars"]) and len(saved["nodes"][0]) == 2
