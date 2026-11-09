"""test_box_editor.py — drawing and resizing boxes in the 3-D editor (To do item 27).

A box is drawn by two corners of its footprint on the work plane with a set height, a
selected unrotated box gets face handles that move and resize it, values snap to the grid
step when one is set, and every role has a colour in both editors.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from toporia_core.framework.problem.regions import ROLES  # noqa: E402
from toporia_core.framework.problem.scenario import Scenario  # noqa: E402
from toporia_gui.geometry import (  # noqa: E402
    COLOURS,
    box_from_corners,
    make_object,
    object_from_bounds,
    resizable,
    snap,
)


def test_a_box_is_drawn_from_two_corners_on_the_work_plane():
    assert box_from_corners((30.0, 5.0), (10.0, 15.0), 2.0, 8.0) == ([10.0, 5.0, 2.0], [20.0, 10.0, 8.0])
    low, size = box_from_corners((10.2, 4.9), (19.6, 15.4), 0.3, 7.7, step=1.0)
    assert low == [10.0, 5.0, 0.0] and size == [10.0, 10.0, 8.0]
    assert box_from_corners((5.0, 5.0), (5.0, 9.0), 0.0, 4.0, step=0.5)[1][0] == 0.5    # never flat
    assert snap(2.26, 0.5) == 2.5 and snap(2.26, 0) == 2.26


def test_face_handles_move_and_resize_an_unrotated_box():
    box = make_object("box", (0, 0, 0), (10, 10, 10), "void")
    assert resizable(box)
    assert not resizable({**box, "rotation": [0, 0, 30]}) and not resizable(make_object("sphere"))
    moved = object_from_bounds(box, (2.2, 14.6, -0.1, 9.8, 3.0, 5.1), step=0.5)
    assert moved["position"] == [2.0, 0.0, 3.0] and moved["size"] == [12.5, 10.0, 2.0]
    assert moved["id"] == box["id"] and box["position"] == [0, 0, 0]       # a new object; the old one untouched


def test_every_role_has_a_colour_in_both_editors():
    from toporia_gui import editor, spatial_view
    assert set(ROLES) <= set(COLOURS)
    assert editor.COLOURS is COLOURS and spatial_view.COLOURS is COLOURS


def test_the_editor_draws_a_box_by_two_clicks():
    from toporia_gui.editor import ProblemEditor
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    editor = ProblemEditor()
    editor.load(Scenario(Lx=40.0, Ly=20.0, Lz=10.0, regions=[]), [], False)
    editor.set_tool("box")
    editor.spatial.tool = "box"
    editor.box_height.setValue(4.0)
    editor.snap_step.setValue(1.0)
    editor.plane_z.setValue(2.0)
    editor._place_spatial([5.3, 2.2, 2.0])
    assert editor.objects == [] and "opposite corner" in editor.hint.text()
    editor._place_spatial([15.1, 12.4, 2.0])
    (box,) = editor.objects
    assert box["shape"] == "box" and box["position"] == [5.0, 2.0, 2.0] and box["size"] == [10.0, 10.0, 4.0]
    assert editor.spatial.snap_step == 1.0
    editor.deleteLater()
    app.processEvents()


def test_a_selected_box_gets_face_handles_in_a_real_viewport():
    pv = pytest.importorskip("pyvista")
    from toporia_gui.spatial_view import SpatialView
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    view = SpatialView()
    try:
        view.plotter = pv.Plotter(off_screen=True)
    except Exception as error:                                  # no rendering context at all
        pytest.skip(f"VTK cannot render here: {error}")
    box = make_object("box", (5, 5, 0), (10, 5, 4), "solid")
    ball = make_object("sphere", (25, 10, 5), (4, 4, 4), "void")
    view.load(Scenario(Lx=40.0, Ly=20.0, Lz=10.0, regions=[box, ball]), [box, ball], False)
    view.select(box["id"])
    assert view.gizmo is not None and not hasattr(view.gizmo, "remove")          # a VTK box widget
    view.select(ball["id"])
    assert hasattr(view.gizmo, "remove")                                        # the move/rotate gizmo
    view.plotter.close()
    view.plotter = None
    view.deleteLater()
    app.processEvents()
