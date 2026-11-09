"""test_unstructured.py — density optimisation on an unstructured triangle mesh (Wave 5).

The mesh follows the domain's edges and a round hole's rim, supports and loads land on its
nodes with the load's total kept, the constant-strain element and the filtered sensitivity
are exact, a run lowers the compliance at the volume budget, and the triangles are saved
and drawn as the design.
"""

import json
from dataclasses import replace

import numpy as np
import pytest

from toporia_core.engine.loop import initialized_method, run_single
from toporia_core.framework.problem.mesh import make_problem
from toporia_library.physics.t3_mesh import build_mesh, element_matrices
from toporia_library.problems import get_run

PRESET = "MBB Beam with a Hole (Triangles)"


def test_the_mesh_follows_the_hole_and_keeps_the_boundary_conditions():
    run = get_run(PRESET)
    problem = make_problem(run.scenario, run.solver.m)
    mesh = build_mesh(problem, 1.5)
    distance = np.hypot(mesh.centroids[:, 0] - 30.0, mesh.centroids[:, 1] - 10.0)
    assert distance.min() > 4.0                                            # nothing inside the hole
    rim = np.abs(np.hypot(mesh.nodes[:, 0] - 30.0, mesh.nodes[:, 1] - 10.0) - 4.0) < 1e-6
    assert rim.sum() >= 16                                                 # nodes on the rim itself
    assert mesh.areas.sum() == pytest.approx(60 * 20 - np.pi * 16, rel=0.02)
    assert mesh.forces[0].sum() == pytest.approx(-1.0) and mesh.fixed.size > 0


def test_a_constant_strain_triangle_is_exact_for_a_uniform_stretch():
    run = get_run("MBB Beam")
    problem = make_problem(run.scenario, run.solver.m)
    mesh = build_mesh(problem, 5.0)
    KE = element_matrices(mesh, 0.3)
    # A rigid translation stores no energy; a uniform stretch ε_xx = 1 stores A·E/(1−ν²)/2·2 per triangle.
    shift = np.tile([1.0, 0.0], 3)
    assert np.allclose(np.einsum("i,eij,j->e", shift, KE, shift), 0.0, atol=1e-10)
    corners = mesh.nodes[mesh.triangles]
    stretch = np.zeros((len(corners), 6))
    stretch[:, 0::2] = corners[:, :, 0]
    energy = np.einsum("ei,eij,ej->e", stretch, KE, stretch)
    assert np.allclose(energy, mesh.areas / (1 - 0.3 ** 2))


def test_the_filtered_sensitivity_is_exact():
    method = initialized_method(get_run(PRESET).updated(max_iter=2, tol=0.0))
    rng = np.random.default_rng(9)
    x = np.where(method.mesh.passive, 1.0, rng.uniform(0.3, 0.9, len(method.x)))

    def compliance(values):
        return method._solve(method._filter(values))[0]

    _, dc_physical = method._solve(method._filter(x))
    dc = method.H.T @ (np.where(method.mesh.passive, 0.0, dc_physical) / method.Hs)
    for e in np.argsort(-np.abs(dc))[:4]:
        up, down = x.copy(), x.copy()
        up[e] += 1e-4
        down[e] -= 1e-4
        assert dc[e] == pytest.approx((compliance(up) - compliance(down)) / 2e-4, rel=1e-4)


def test_a_run_lowers_the_compliance_at_the_budget_and_saves_its_triangles(tmp_path):
    run = get_run(PRESET).updated(max_iter=20, tol=0.0, save_every=0).with_output_dir(tmp_path)
    run_single(run)
    mesh = json.loads((tmp_path / "mesh.json").read_text())
    assert len(mesh["triangles"]) == len(mesh["values"]) > 500 and len(mesh["nodes"][0]) == 2
    method = initialized_method(get_run(PRESET).updated(max_iter=10, tol=0.0))
    values = []
    for i in range(1, 11):
        method.step(i)
        values.append(method.get_responses())
    assert values[-1]["objective"] < values[0]["objective"]
    assert values[-1]["mesh_volume"] == pytest.approx(0.5, abs=2e-3)
    assert method.get_density().shape == make_problem(run.scenario, run.solver.m).shape


def test_the_triangles_are_drawn_as_the_design():
    pytest.importorskip("PySide6.QtWidgets")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from matplotlib.collections import PolyCollection

    from toporia_gui.canvas import LiveCanvas
    from toporia_gui.display_options import DEFAULTS
    method = initialized_method(get_run(PRESET).updated(max_iter=1, tol=0.0))
    canvas = LiveCanvas()
    canvas.set_display(DEFAULTS)
    from toporia_core.engine.loop import network_document
    canvas.set_mesh(network_document(method.mesh_view()), width=60.0)
    canvas.refresh(method.get_density(), [1.0], 1)
    assert any(isinstance(a, PolyCollection) for a in canvas._overlay) and canvas._im.get_alpha() == 0.0


def test_only_two_dimensional_problems():
    run = get_run("Cantilever 3D").updated(method="unstructured")
    with pytest.raises(ValueError):
        initialized_method(replace(run, solver=replace(run.solver, filter_specs=[])))
