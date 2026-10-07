"""test_3d.py — the 3-D problem, the H8 engine, and every part that works in 3-D.

The decisive check is the first: with Poisson's ratio 0, a design that does
not vary through the depth must behave exactly as the 2-D design in plane
stress, so the 3-D compliance is the 2-D one divided by the depth.  That
checks the brick's stiffness, the assembly, the supports and the way loads
are shared through the depth at once, to machine precision.
"""

import json
import re
import struct
from dataclasses import replace

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single_with_store
from toporia.framework.problem.mesh import BoxProblem, RectangularProblem, make_problem, projection
from toporia.plugins.interpolations.simp import SIMP
from toporia.plugins.physics.h8_solid import H8Solid, element_stiffness
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
from toporia.plugins.problems import get_run


def _quick(**values):
    return get_run("Cantilever 3D").updated(**{"save_every": 0, **values})


def _compliance(engine, density):
    state = engine.solve(density)
    return sum(w * engine.compliance(state, k) for k, w in enumerate(state.weights))


# ── The problem ───────────────────────────────────────────────────────────────

def test_a_depth_makes_the_problem_three_dimensional():
    scenario = get_run("MBB Beam").scenario
    assert isinstance(make_problem(scenario, 0.4), RectangularProblem)
    box = make_problem(replace(scenario, Lz=10.0), 0.4)
    assert isinstance(box, BoxProblem) and box.dims == 3
    assert box.shape == (4, 8, 24) and box.fixed_x_nodes.shape == (5, 9, 25)
    # A 2-D roller is a wall through the depth: it holds z too, so the box cannot slide out of plane.
    assert np.array_equal(box.fixed_z_nodes, box.fixed_x_nodes | box.fixed_y_nodes)
    assert box.layer_weights.tolist() == [0.125, 0.25, 0.25, 0.25, 0.125]


def test_holes_go_through_the_depth():
    scenario = replace(get_run("Drone Arm").scenario, Lz=6.0)
    box, section = make_problem(scenario, 0.3), make_problem(get_run("Drone Arm").scenario, 0.3)
    for layer in box.void_elements:
        assert np.array_equal(layer, section.void_elements)


# ── The H8 engine ─────────────────────────────────────────────────────────────

def test_the_brick_moves_freely_in_exactly_six_ways():
    values = np.linalg.eigvalsh(element_stiffness(0.3, 1.0, 2.0, 0.5))
    assert np.sum(np.abs(values) < 1e-10) == 6 and values[6] > 0


@pytest.mark.parametrize("name", ["Cantilever", "MBB Beam", "Drone Arm"])
def test_an_extruded_design_is_the_plane_design_divided_by_the_depth(name):
    plane = replace(get_run(name).scenario, nu=0.0)
    p2, p3 = make_problem(plane, 0.4), make_problem(replace(plane, Lz=7.0), 0.4)
    density = np.clip(np.random.default_rng(0).uniform(0.1, 1.0, p2.shape), p2.lower_bound, p2.upper_bound)
    q4, h8 = Q4PlaneStress(), H8Solid()
    q4.initialize(p2, {}, SIMP())
    h8.initialize(p3, {"linear_solver": "direct"}, SIMP())
    c2 = _compliance(q4, density)
    c3 = _compliance(h8, np.broadcast_to(density, p3.shape).copy())
    assert c3 == pytest.approx(c2 / 7.0, rel=1e-9)


def test_multigrid_gives_the_direct_answer():
    pytest.importorskip("pyamg")
    problem = make_problem(_quick().scenario, 0.4)
    density = np.random.default_rng(1).uniform(0.2, 1.0, problem.shape)
    results = []
    for solver in ("direct", "amg"):
        engine = H8Solid()
        engine.initialize(problem, {"linear_solver": solver, "amg_above": 0, "amg_tol": 1e-10}, SIMP())
        assert engine.use_amg == (solver == "amg")
        results.append(_compliance(engine, density))
    assert results[1] == pytest.approx(results[0], rel=1e-7)


# ── Runs ──────────────────────────────────────────────────────────────────────

def test_the_quick_3d_case_optimises(tmp_path):
    store, density = run_single_with_store(_quick(max_iter=25).with_output_dir(tmp_path))
    assert density.shape == (4, 8, 24)
    assert store.objectives[-1] < 0.5 * store.objectives[0]
    assert density.mean() == pytest.approx(0.3, abs=0.01)
    assert np.array_equal(np.load(tmp_path / "final_density.npy"), density)
    assert (tmp_path / "final_density.png").exists()
    assert projection(density).shape == (8, 24)


@pytest.mark.parametrize("method", ["h8+mma", "h8+simpl", "h8+beso"])
def test_every_kind_of_updater_works_in_3d(method):
    run = _quick(method=method, max_iter=4, tol=0.0)
    method_obj = initialized_method(run)
    for iteration in range(1, 5):
        method_obj.step(iteration)
    assert np.all(np.isfinite(method_obj.get_density()))


def test_a_stress_constraint_and_a_projection_work_in_3d():
    run = _quick(method="h8+scipy_slsqp", max_iter=4, tol=0.0, objective={"type": "volume"},
                 constraints=[{"type": "stress", "limit": 50.0}],
                 filter_specs=[{"type": "density"}, {"type": "heaviside"}])
    method = initialized_method(run)
    try:
        for iteration in range(1, 5):
            method.step(iteration)
        assert "max_stress" in method.get_responses()
    finally:
        method.close()                      # SLSQP runs in a background thread


@pytest.mark.parametrize("values, part", [
    ({"method": "q4+oc"}, "2-D Q4 plane stress"),
    ({"filter_specs": [{"type": "am"}]}, "AM overhang filter"),
    ({"method": "levelset"}, "RBF level set"),
    ({"method": "h8+mma", "representation": {"type": "mmc"}}, "Moving morphable components"),
    ({"postprocess": [{"type": "export_dxf"}]}, "Export outline (DXF)"),
])
def test_a_part_that_works_in_2d_only_is_refused_with_what_can(values, part):
    with pytest.raises(ValueError, match=re.escape(part) + ".* works in 2-D only, and this problem is 3-D"):
        initialized_method(_quick(**values))


def test_the_3d_engine_is_refused_in_2d():
    with pytest.raises(ValueError, match="works in 3-D only, and this problem is 2-D"):
        initialized_method(get_run("Cantilever").updated(method="h8+oc"))


def test_post_processing_in_3d(tmp_path):
    run = _quick(max_iter=15, postprocess=[{"type": t} for t in
                                           ("threshold", "connectivity", "feature_size", "export_stl")])
    store, density = run_single_with_store(run.with_output_dir(tmp_path))
    post = store.postprocess
    assert post["threshold"]["metrics"]["volume"] == pytest.approx(density.mean(), abs=0.01)
    assert (tmp_path / "post" / "thresholded.npy").exists()
    assert post["connectivity"]["metrics"]["pieces"] >= 1
    assert post["feature_size"]["metrics"]["min_member_mm"] is not None
    data = (tmp_path / "post" / "design.stl").read_bytes()
    assert struct.unpack("<I", data[80:84])[0] == post["export_stl"]["metrics"]["triangles"] > 0
    record = json.loads((tmp_path / "run.json").read_text())
    assert record["scenario"]["definition"]["Lz"] == 10.0


def test_a_saved_3d_run_can_be_post_processed_again(tmp_path):
    from toporia.engine.postprocess import postprocess_folder
    run_single_with_store(_quick(max_iter=5).with_output_dir(tmp_path))
    done = postprocess_folder(tmp_path, [{"type": "threshold"}])
    assert done["threshold"]["metrics"]["volume"] == pytest.approx(0.3, abs=0.01)
