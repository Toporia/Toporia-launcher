"""test_truss.py — the ground-structure truss, its nodes and its clean solid (To do item 3).

The ground structure has no overlapping bars and none through holes, its supports and loads
land on nodes, the stiffness and frequency gradients are exact, Toporia's own joint and
anchored nodes do what they say, the design stays bars, and the post-processor makes a
clean solid from them only when asked, in 2-D and 3-D.
"""

import json
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from toporia_core.engine.loop import initialized_method, network_document, run_single
from toporia_core.framework import HoleConfig
from toporia_core.framework.problem.mesh import make_problem
from toporia_core.framework.problem.run import Output
from toporia_library.physics.truss import TrussSolver, bars_to_density, ground_structure
from toporia_library.problems import get_run


def _mbb_problem(**changes):
    run = get_run("MBB Beam")
    return make_problem(replace(run.scenario, **changes), run.solver.m)


def _method(name="MBB Beam (Truss)", objective=None, scenario=None, **params):
    run = get_run(name).updated(tol=0.0)
    run = replace(run, solver=replace(run.solver, method_params={**run.solver.method_params, "spacing": 10.0,
                                                                 **params}))
    if objective or scenario:
        run = replace(run, scenario=replace(scenario or run.scenario,
                                            objective=objective or run.scenario.objective))
    return initialized_method(run), run


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


def test_the_record_drawing_of_a_truss():
    problem = _mbb_problem()
    structure = ground_structure(problem, spacing=10.0, reach=1)
    areas = np.zeros(len(structure.bars))
    horizontal = np.flatnonzero(np.isclose(np.abs(structure.directions[:, 0]), 1.0))[0]
    areas[horizontal] = 2.0                     # one bar, 2 mm wide
    density = bars_to_density(problem, structure, areas)
    (i, _) = structure.bars[horizontal]
    row = int(min(structure.nodes[i, 1] // problem.dy, problem.nely - 1))
    assert density.shape == problem.shape and density.max() == pytest.approx(1.0)
    assert density[row].sum() > 5 and density.sum() < 40


def test_the_frequency_gradient_is_exact_with_joint_mass():
    from toporia_library.physics.truss_nodes import lumped_mass
    method, _ = _method(objective={"type": "eigenfrequency"}, joint_length=1.5)
    areas = np.random.default_rng(6).uniform(0.5, 2.0, len(method.areas))
    density, joint = method.settings["mass_density"], method.settings["joint_length"]

    def lowest(a):
        return method.fe.lowest_mode(a, lumped_mass(method.structure, a, density, joint), method.mass_slope)

    _, _, slope = lowest(areas)
    for i in np.argsort(-np.abs(slope))[:4]:
        step = 1e-6 * areas[i]
        up, down = areas.copy(), areas.copy()
        up[i] += step
        down[i] -= step
        assert slope[i] == pytest.approx((lowest(up)[0] - lowest(down)[0]) / (2 * step), rel=1e-4)


def test_a_frequency_run_raises_the_lowest_frequency():
    method, _ = _method(objective={"type": "eigenfrequency"})
    frequencies = []
    for i in range(1, 9):
        method.step(i)
        frequencies.append(method.get_responses()["frequency"])
    assert frequencies[-1] > frequencies[0]


def test_joints_take_volume_and_mass():
    pins, _ = _method()
    joints, _ = _method(joint_length=2.0)
    assert np.allclose(joints.material_lengths, pins.material_lengths + 4.0)
    for i in range(1, 4):
        joints.step(i)
    assert float(joints.areas @ joints.material_lengths) == pytest.approx(joints.volume_limit, rel=1e-6)
    assert "joint_radius" in joints.network() and "joint_radius" not in pins.network()


def test_anchored_nodes_stiffen_the_truss():
    free, _ = _method()
    anchored, _ = _method(anchor_stiffness=0.05)
    areas = free.areas.copy()
    assert anchored.fe.solve(areas)[1] < free.fe.solve(areas)[1]


def test_a_spring_object_anchors_only_its_nodes():
    from toporia_gui.geometry import make_object, objects_from_scenario
    run = get_run("MBB Beam (Truss)")
    objects = objects_from_scenario(run.scenario)
    objects.append(make_object(position=(30.0, 0.0, 0.0), role="spring", axes=["y"], stiffness=0.2))
    method, _ = _method(scenario=replace(run.scenario, regions=objects))
    anchored = np.flatnonzero(method.fe.springs)
    assert len(anchored) == 1 and anchored[0] % 2 == 1                  # one node, its y DOF
    node = method.structure.nodes[anchored[0] // 2]
    assert node[0] == pytest.approx(30.0) and node[1] == pytest.approx(0.0)


def test_a_node_carries_a_value_of_your_own():
    method, _ = _method(node_value="force / (joint_area + 1)")
    method.step(1)
    network = method.network()
    assert network["node_label"] == "force / (joint_area + 1)"
    assert len(network["node_values"]) == len(network["nodes"]) and np.all(np.isfinite(network["node_values"]))
    with pytest.raises(ValueError, match="not a variable here"):
        _method(node_value="stress * 2")


def test_the_design_stays_bars_and_a_solid_is_made_only_when_asked(tmp_path):
    run = get_run("MBB Beam (Truss)").updated(max_iter=15, tol=0.0, save_every=0)
    asked = replace(run, output=Output(dir=tmp_path / "a", postprocess=[{"type": "truss_solid"}]))
    run_single(asked.with_output_dir(tmp_path / "a"))
    metrics = json.loads((tmp_path / "a" / "run.json").read_text())["postprocess"]["truss_solid"]["metrics"]
    lines = (tmp_path / "a" / "post" / "truss_solid.dxf").read_text().split("\n")
    assert metrics["bars"] > 5 and metrics["outlines"] >= 1 and lines.count("POLYLINE") == metrics["outlines"]
    assert (tmp_path / "a" / "post" / "truss_solid.svg").exists()
    # The outline stays inside the design domain.
    xs = [float(v) for k, v in zip(lines, lines[1:], strict=False) if k == "10"]
    ys = [float(v) for k, v in zip(lines, lines[1:], strict=False) if k == "20"]
    assert min(xs) >= -1e-6 and max(xs) <= 60 + 1e-6 and min(ys) >= -1e-6 and max(ys) <= 20 + 1e-6

    bare = replace(run, output=Output(dir=tmp_path / "b"))
    run_single(bare.with_output_dir(tmp_path / "b"))
    assert not (tmp_path / "b" / "post").exists()                      # no step, nothing made
    assert json.loads((tmp_path / "b" / "network.json").read_text())["bars"]


def test_a_solid_can_be_made_later_from_a_saved_truss(tmp_path):
    from toporia_core.engine.postprocess import postprocess_folder
    run = get_run("MBB Beam (Truss)").updated(max_iter=10, tol=0.0, save_every=0)
    run_single(replace(run, output=Output(dir=tmp_path)).with_output_dir(tmp_path))
    done = postprocess_folder(tmp_path, [{"type": "truss_solid"}])
    assert done["truss_solid"]["metrics"]["bars"] > 0 and (tmp_path / "post" / "truss_solid.dxf").exists()


def test_a_space_truss_becomes_an_stl():
    pytest.importorskip("skimage")
    from toporia_core.framework.parts.postprocess import Result
    from toporia_library.postprocessors.truss_solid import TrussSolid
    method, run = _method("Cantilever 3D (Truss)")
    for i in range(1, 6):
        method.step(i)
    folder = Path(tempfile.mkdtemp())
    result = Result(density=method.get_density(), problem=method.problem, run=run, folder=folder,
                    network=network_document(method.network()))
    metrics = TrussSolid().process(result)
    assert metrics["triangles"] > 100 and (folder / "truss_solid.stl").stat().st_size > 84


def test_a_run_saves_its_truss_and_sends_it_while_running(tmp_path):
    run = get_run("MBB Beam (Truss)").updated(max_iter=4, tol=0.0, save_every=0)
    run = replace(run, output=Output(dir=tmp_path), solver=replace(
        run.solver, method_params={**run.solver.method_params, "spacing": 10.0})).with_output_dir(tmp_path)
    sent = []

    def on_iteration(density, objectives, number):
        pass

    on_iteration.on_network = sent.append
    run_single(run, on_iteration)
    saved = json.loads((tmp_path / "network.json").read_text())
    assert len(sent) == 4 and {"nodes", "bars", "areas", "forces", "node_values"} <= set(saved)
    assert len(saved["areas"]) == len(saved["bars"]) and len(saved["nodes"][0]) == 2
