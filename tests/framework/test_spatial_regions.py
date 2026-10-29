"""Real H8 spatial masks and embedded STL assignments, not extruded XY fallbacks."""

from dataclasses import replace

import numpy as np
import pytest

from toporia.apps.gui.geometry import make_object, objects_from_scenario
from toporia.framework.problem.mesh import make_problem
from toporia.framework.problem.run import Run
from toporia.framework.problem.scenario import Scenario
from toporia.framework.problem.solver import Solver
from toporia.plugins.physics.h8_solid import H8DofLayout
from toporia.plugins.problems import get_run


def spatial_objects():
    return [make_object("box", (0, 0, 0), (0, 4, 4), "support", axes=["x", "y", "z"]),
            make_object("point", (10, 2, 3), role="load", force=[0, 0, -5])]


def scenario():
    return Scenario(Lx=10, Ly=4, Lz=4, regions=spatial_objects())


def test_spatial_point_load_is_one_node_not_a_through_depth_line():
    problem = make_problem(scenario())
    assert problem.load_node_sets[0].sum() == 1
    assert problem.fixed_z_nodes[:, :, 0].all()
    forces = H8DofLayout(problem).forces[0][1].reshape(-1, 3)
    np.testing.assert_allclose(forces.sum(axis=0), [0, 0, -5])
    assert np.count_nonzero(forces[:, 2]) == 1


def test_spatial_regions_and_force_totals_are_resolution_independent():
    for m in (.5, 1, 2):
        problem = make_problem(scenario(), m)
        force = H8DofLayout(problem).forces[0][1].reshape(-1, 3)
        np.testing.assert_allclose(force.sum(axis=0), [0, 0, -5])


def test_legacy_extrusion_copy_keeps_h8_supports_and_layer_force_shares():
    original = get_run("Cantilever 3D").scenario
    legacy = H8DofLayout(make_problem(original, .2))
    copied = replace(original, regions=objects_from_scenario(original))
    explicit = H8DofLayout(make_problem(copied, .2))
    np.testing.assert_array_equal(explicit.fixed_dofs, legacy.fixed_dofs)
    np.testing.assert_allclose(explicit.forces[0][1], legacy.forces[0][1], atol=1e-14)


def test_h8_optimizer_accepts_true_spatial_definition(tmp_path):
    from toporia.engine.loop import run_single
    run = Run(scenario=scenario(), solver=Solver(method="h8+oc", m=.5, max_iter=2, filter_specs=[{"type": "density"}]))
    density = run_single(run.with_output_dir(tmp_path))
    assert density.shape == (2, 2, 5)
    assert np.isfinite(density).all()


def test_stl_can_define_support_load_domain_and_solid_void_regions(tmp_path):
    pv = pytest.importorskip("pyvista")
    from toporia.apps.gui.geometry_import import import_stl
    from toporia.apps.gui.project import ProblemDocument
    path = tmp_path / "patch.stl"
    pv.Cube(bounds=(-.1, .1, 0, 4, 0, 4)).triangulate().save(path)
    support = import_stl(path, "support")
    support["axes"] = ["x", "y", "z"]
    pv.Cube(bounds=(9.9, 10.1, 1, 3, 1, 3)).triangulate().save(path)
    load = import_stl(path, "load")
    load["force"] = [0, -12, 0]
    pv.Cube(bounds=(0, 10, 0, 4, 0, 4)).triangulate().save(path)
    domain = import_stl(path, "domain")
    pv.Cube(bounds=(2, 3, 1, 2, 1, 2)).triangulate().save(path)
    void = import_stl(path, "void")
    custom = replace(scenario(), regions=[support, load, domain, void])
    problem = make_problem(custom)
    assert problem.void_elements.sum() == 1
    assert problem.load_node_sets[0].sum() == 9
    force = H8DofLayout(problem).forces[0][1].reshape(-1, 3)
    np.testing.assert_allclose(force.sum(axis=0), [0, -12, 0])
    portable = ProblemDocument(custom, custom.regions).save(tmp_path / "portable.pro")
    path.unlink()
    restored = ProblemDocument.load(portable)
    np.testing.assert_array_equal(make_problem(restored.scenario).void_elements, problem.void_elements)
    solid = {**void, "role": "solid"}
    assert make_problem(replace(custom, regions=[support, load, domain, solid])).passive_elements.sum() == 1


def test_open_stl_is_a_surface_patch_and_cannot_be_a_volume(tmp_path):
    pv = pytest.importorskip("pyvista")
    from toporia.apps.gui.geometry_import import import_stl
    path = tmp_path / "face.stl"
    pv.Plane(center=(10, 2, 2), direction=(1, 0, 0), i_size=4, j_size=4).triangulate().save(path)
    patch = import_stl(path, "load")
    assert patch["sampling"] == "surface"
    patch["force"] = [0, 0, -9]
    problem = make_problem(replace(scenario(), regions=[spatial_objects()[0], patch]))
    assert problem.load_node_sets[0].sum() > 1
    with pytest.raises(ValueError, match="closed|surface|volume"):
        make_problem(replace(scenario(), regions=[*spatial_objects(), {**patch, "role": "void"}]))
