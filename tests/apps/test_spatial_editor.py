"""Spatial editor state, transforms and imports without requiring a native GPU window."""

import os
from dataclasses import replace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from toporia.apps.gui.editor import ProblemEditor
from toporia.apps.gui.geometry import make_object
from toporia.apps.gui.project import Project
from toporia.apps.gui.spatial_view import object_mesh, transformed_object
from toporia.framework.problem.run import Run
from toporia.framework.problem.scenario import Scenario
from toporia.framework.problem.spatial import rotation_matrix


@pytest.fixture(scope="module")
def editor():
    app = QApplication.instance() or QApplication([])
    editor = ProblemEditor()
    yield editor
    editor.deleteLater()
    app.processEvents()


def test_xyz_inspector_and_gizmo_share_undoable_physical_objects(editor):
    editor.load(Scenario(Lz=20), [], False)
    editor.set_tool("box")
    editor._place_spatial([10, 12, 3])
    assert editor.viewport_stack.currentWidget() is editor.spatial
    obj = editor.objects[0]
    assert obj["position"] == [10, 12, 3]
    editor.fields["z"].setValue(6)
    editor.fields["rx"].setValue(30)
    editor.fields["fz"].setValue(-9)
    editor.role.setCurrentIndex(editor.role.findData("load"))
    editor.apply_inspector()
    edited = editor.objects[0]
    assert edited["position"][2] == 6 and edited["rotation"][0] == 30
    assert edited["force"][2] == -9
    delta = np.eye(4)
    delta[:3, 3] = [1, 2, 3]
    editor._spatial_transform(transformed_object(edited, delta))
    assert editor.objects[0]["position"] == [11, 14, 9]
    editor.undo()
    assert editor.objects[0] == edited


@pytest.mark.parametrize("shape", ["point", "line", "rectangle", "circle", "box", "sphere", "cylinder"])
def test_display_geometry_obeys_world_transform(shape):
    pytest.importorskip("pyvista")
    obj = make_object(shape, (10, 12, 3), (2, 3, 4), rotation=[0, 0, 90])
    mesh = object_mesh(obj)
    assert mesh.n_points > 0
    assert np.isfinite(mesh.points).all()
    if shape == "box":
        np.testing.assert_allclose(mesh.bounds, [7, 10, 12, 14, 3, 7], atol=1e-6)


def test_gizmo_rotation_is_composed_with_object_rotation():
    original = make_object("box", (2, 0, 0), (1, 2, 3), rotation=[0, 0, 30])
    matrix = np.eye(4)
    matrix[:3, :3] = rotation_matrix([0, 0, 60])
    transformed = transformed_object(original, matrix)
    np.testing.assert_allclose(transformed["position"], [1, np.sqrt(3), 0], atol=1e-12)
    np.testing.assert_allclose(transformed["rotation"], [0, 0, 90], atol=1e-12)


def test_stl_import_editor_role_and_project_are_portable(editor, tmp_path):
    pv = pytest.importorskip("pyvista")
    path = tmp_path / "fixture.stl"
    pv.Cube().triangulate().save(path)
    editor.load(Scenario(Lz=20), [], False)
    editor.import_geometry(path)
    assert editor.objects[0]["shape"] == "stl"
    editor.role.setCurrentIndex(editor.role.findData("support"))
    for check in editor.axes.values():
        check.setChecked(True)
    editor.apply_inspector()
    project = Project("STL assignment", Run(scenario=replace(editor.scenario, regions=editor.objects)), objects=editor.objects)
    saved = project.save(tmp_path / "project.top")
    path.unlink()
    restored = Project.load(saved)
    assert restored.objects == editor.objects
    assert restored.objects[0]["axes"] == ["x", "y", "z"]


def test_dxf_profiles_become_independent_planar_regions(editor, tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new()
    doc.modelspace().add_lwpolyline([(2, 2), (4, 2), (4, 4), (2, 4)], close=True)
    path = tmp_path / "profile.dxf"
    doc.saveas(path)
    editor.load(Scenario(), [], False)
    editor.import_geometry(path)
    assert editor.objects[0]["shape"] == "polygon"
    assert editor.objects[0]["vertices"] == [[2., 2.], [4., 2.], [4., 4.], [2., 4.]]
    editor.undo()
    assert editor.objects == []
