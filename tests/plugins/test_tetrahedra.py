"""test_tetrahedra.py — 3-D unstructured meshes (Wave 5): tetrahedra fitted to curved voids.

The mesh has no inverted or flattened tetrahedra, its nodes lie on the voids, its volume
converges to the exact domain volume at second order, its stiffness agrees with Timoshenko
beam theory as it is refined, the filtered sensitivity is exact, a run lowers the
compliance at the budget, and the fitted boundary is a closed STL.
"""

import json
from dataclasses import replace

import numpy as np
import pytest

from toporia_core.engine.loop import initialized_method, run_single
from toporia_core.framework import EdgeConstraint, HoleConfig, LoadCase, PointLoad, Scenario
from toporia_core.framework.problem.mesh import make_problem
from toporia_library.physics.tet_mesh import build_tet_mesh, solid_surface, tet_element_matrices
from toporia_library.problems import get_run

HOLE = "Cantilever 3D with a Hole (Tetrahedra)"
SPHERE = "Block around a Spherical Void (Tetrahedra)"


def test_the_mesh_follows_a_bore_and_its_volume_converges_at_second_order():
    run = get_run(HOLE)
    problem = make_problem(run.scenario, run.solver.m)
    exact = 60 * 20 * 10 - np.pi * 4 ** 2 * 10
    errors = []
    for size in (2.0, 1.0):
        mesh = build_tet_mesh(problem, size)
        assert mesh.volumes.min() > 0.25 * size ** 3 / 6                   # no flat or inverted tetrahedra
        assert np.hypot(mesh.centroids[:, 0] - 20, mesh.centroids[:, 1] - 10).min() > 4.0
        errors.append(abs(mesh.volumes.sum() - exact) / exact)
    assert errors[1] < errors[0] / 3 and errors[1] < 1e-3                  # about four times smaller per halving


def test_nodes_are_snapped_onto_a_sphere():
    run = get_run(SPHERE)
    problem = make_problem(run.scenario, run.solver.m)
    mesh = build_tet_mesh(problem, 2.0)
    centre = np.array([20.0, 10.0, 10.0])
    radius = np.linalg.norm(mesh.nodes - centre, axis=1)
    assert np.sum(np.abs(radius - 5.0) < 1e-6) >= 50                       # many nodes on the sphere itself
    assert np.linalg.norm(mesh.centroids - centre, axis=1).min() > 5.0     # nothing inside it


def _beam(size):
    """A clamped 100 x 10 x 10 beam with a unit downward load at its free end."""
    scenario = Scenario(Lx=100.0, Ly=10.0, Lz=10.0, edge_constraints=[EdgeConstraint(edge="left", dof="both")],
                        point_loads=[PointLoad(x=100.0, y=5.0)], load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],
                        volfrac=1.0)
    run = get_run(HOLE).updated(tol=0.0)
    run = replace(run, scenario=scenario, solver=replace(run.solver, m=1.0, method_params={"element_size": size,
                                                                                         "rmin": 0.0}))
    method = initialized_method(run)
    return method._solve(np.ones(len(method.x)))[0]


def test_tetrahedra_agree_with_timoshenko_beam_theory():
    E, nu, F, L, b, h = 1.0, 0.3, 1.0, 100.0, 10.0, 10.0
    inertia, area, G = b * h ** 3 / 12, b * h, E / (2 * (1 + nu))
    theory = F * L ** 3 / (3 * E * inertia) + F * L / ((5 / 6) * G * area)      # compliance = F · tip deflection
    coarse, fine = _beam(2.5), _beam(1.25)
    # Linear tetrahedra are too stiff and converge from below in compliance.
    assert coarse < fine < theory * 1.02
    assert abs(fine - theory) / theory < 0.1 and abs(fine - theory) < abs(coarse - theory)


def test_the_element_is_exact_for_rigid_motion_and_uniform_strain():
    run = get_run(HOLE)
    mesh = build_tet_mesh(make_problem(run.scenario, run.solver.m), 4.0)
    KE = tet_element_matrices(mesh, 0.3)
    shift = np.tile([0.3, -0.2, 0.5], 4)
    assert np.allclose(np.einsum("i,eij,j->e", shift, KE, shift), 0.0, atol=1e-10)
    corners = mesh.nodes[mesh.tets]
    stretch = np.zeros((len(corners), 12))
    stretch[:, 0::3] = corners[:, :, 0]                                     # u = x: ε_xx = 1
    lam, mu = 0.3 / (1.3 * 0.4), 1 / (2 * 1.3)
    assert np.allclose(np.einsum("ei,eij,ej->e", stretch, KE, stretch), mesh.volumes * (lam + 2 * mu))


def test_the_filtered_sensitivity_is_exact_in_3d():
    method = initialized_method(get_run(HOLE).updated(max_iter=2, tol=0.0))
    x = np.where(method.mesh.passive, 1.0, np.random.default_rng(3).uniform(0.3, 0.9, len(method.x)))

    def compliance(values):
        return method._solve(method._filter(values))[0]

    _, dc_physical = method._solve(method._filter(x))
    dc = method.H.T @ (np.where(method.mesh.passive, 0.0, dc_physical) / method.Hs)
    for e in np.argsort(-np.abs(dc))[:3]:
        up, down = x.copy(), x.copy()
        up[e] += 1e-4
        down[e] -= 1e-4
        assert dc[e] == pytest.approx((compliance(up) - compliance(down)) / 2e-4, rel=1e-4)


def test_a_run_writes_a_closed_fitted_stl(tmp_path):
    run = get_run(HOLE).updated(max_iter=12, tol=0.0, save_every=0).with_output_dir(tmp_path)
    run_single(run)
    record = json.loads((tmp_path / "run.json").read_text())
    faces = record["postprocess"]["mesh_surface"]["metrics"]["faces"]
    data = (tmp_path / "post" / "mesh_surface.stl").read_bytes()
    assert faces > 100 and int.from_bytes(data[80:84], "little") == faces
    mesh = json.loads((tmp_path / "mesh.json").read_text())
    from types import SimpleNamespace
    cells = SimpleNamespace(nodes=np.asarray(mesh["nodes"]), tets=np.asarray(mesh["tetrahedra"]))
    triangles = solid_surface(cells, np.asarray(mesh["values"]))
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    key = np.sort(np.round(edges, 9).view([("", float)] * 3).reshape(edges.shape[:2]), axis=1)
    _, counts = np.unique(key, axis=0, return_counts=True)
    # Closed: every edge in an even number of faces (two, or four where solids touch along an edge).
    assert np.all(counts % 2 == 0)


def test_a_short_3d_run_lowers_the_compliance_at_the_budget():
    method = initialized_method(get_run(HOLE).updated(max_iter=8, tol=0.0))
    values = []
    for i in range(1, 9):
        method.step(i)
        values.append(method.get_responses())
    assert values[-1]["objective"] < values[0]["objective"]
    assert values[-1]["mesh_volume"] == pytest.approx(0.3, abs=3e-3)
    assert method.get_density().ndim == 3


def test_the_2d_mesh_boundary_exports_closed_loops(tmp_path):
    run = get_run("MBB Beam with a Hole (Triangles)").updated(max_iter=10, tol=0.0, save_every=0)
    from toporia_core.framework.problem.run import Output
    run = replace(run, output=Output(dir=tmp_path, postprocess=[{"type": "mesh_surface"}])).with_output_dir(tmp_path)
    run_single(run)
    metrics = json.loads((tmp_path / "run.json").read_text())["postprocess"]["mesh_surface"]["metrics"]
    lines = (tmp_path / "post" / "mesh_surface.dxf").read_text().split("\n")
    assert metrics["loops"] >= 1 and lines.count("POLYLINE") == metrics["loops"]


def test_the_holes_parameter_is_honoured_without_regions():
    scenario = replace(get_run("Cantilever 3D").scenario, holes=[HoleConfig(cx=40.0, cy=10.0, r_void=3.0,
                                                                            r_passive=3.0)])
    mesh = build_tet_mesh(make_problem(scenario, 0.4), 2.0)
    assert np.hypot(mesh.centroids[:, 0] - 40, mesh.centroids[:, 1] - 10).min() > 3.0


def test_the_solid_tetrahedra_are_drawn_in_3d():
    pytest.importorskip("PySide6.QtWidgets")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    from toporia_core.engine.loop import network_document
    from toporia_gui.canvas import LiveCanvas
    from toporia_gui.display_options import DEFAULTS
    method = initialized_method(get_run(HOLE).updated(max_iter=1, tol=0.0))
    method.physical[:] = 1.0
    canvas = LiveCanvas()
    canvas.set_display(DEFAULTS)
    canvas.set_mesh(network_document(method.mesh_view()), width=60.0)
    canvas.refresh(method.get_density(), [1.0], 1)
    canvas.show_3d(method.get_density(), 2.5)
    assert any(isinstance(c, Poly3DCollection) for c in canvas._ax_d.collections)
