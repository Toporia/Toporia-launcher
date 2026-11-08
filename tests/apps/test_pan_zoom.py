"""Every result view zooms about the cursor, pans by dragging and comes back with a double-click."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from matplotlib.backend_bases import MouseEvent  # noqa: E402

from toporia.apps.gui.canvas import LiveCanvas  # noqa: E402


@pytest.fixture
def canvas():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    view = LiveCanvas()
    view.resize(900, 400)
    view.refresh(np.full((20, 60), 0.5), [3.0, 2.0, 1.5], 3)
    view.draw()
    yield view
    view.deleteLater()
    app.processEvents()


def _event(canvas, name, ax, fx, fy, button=1, dblclick=False, step=0):
    """A mouse event at fraction (fx, fy) of `ax`'s box, in display pixels."""
    box = ax.get_window_extent()
    x, y = box.x0 + fx * box.width, box.y0 + fy * box.height
    event = MouseEvent(name, canvas, x, y, button=button, dblclick=dblclick, step=step)
    canvas.callbacks.process(name, event)


def test_the_wheel_zooms_about_the_cursor_and_the_view_survives_the_next_iteration(canvas):
    ax = canvas._ax_d
    width = np.diff(ax.get_xlim())[0]
    _event(canvas, "scroll_event", ax, 0.5, 0.5, button="up", step=1)
    assert np.diff(ax.get_xlim())[0] == pytest.approx(width / 1.2)
    zoomed = ax.get_xlim()
    canvas.refresh(np.full((20, 60), 0.4), [3.0, 2.0, 1.5, 1.4], 4)   # a run keeps drawing
    assert ax.get_xlim() == pytest.approx(zoomed)


def test_dragging_pans_and_a_double_click_restores_the_whole_field(canvas):
    ax = canvas._ax_d
    whole = ax.get_xlim()
    _event(canvas, "button_press_event", ax, 0.5, 0.5)
    _event(canvas, "motion_notify_event", ax, 0.25, 0.5)
    _event(canvas, "button_release_event", ax, 0.25, 0.5)
    assert ax.get_xlim()[0] > whole[0]                              # dragged left: view moved right
    _event(canvas, "button_press_event", ax, 0.5, 0.5, dblclick=True)
    assert ax.get_xlim() == pytest.approx(whole)


def test_the_convergence_curve_zooms_and_resets_too(canvas):
    ax = canvas._ax_c
    _event(canvas, "scroll_event", ax, 0.5, 0.5, button="up", step=1)
    zoomed = np.diff(ax.get_ylim())[0]
    _event(canvas, "button_press_event", ax, 0.5, 0.5, dblclick=True)
    assert np.diff(ax.get_ylim())[0] > zoomed


def test_the_export_step_previews_what_the_file_will_hold(tmp_path):
    from toporia.apps.gui.project import Project
    from toporia.apps.gui.window import MainWindow
    from toporia.plugins.problems import get_run
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow()
    try:
        window._activate_project(Project("Preview", get_run("MBB Beam")))
        window.go_to_step(4)
        assert window.export_info.text() == ""                       # nothing to export yet
        window._result_config = window.current_config().updated(m=0.5)
        density = np.zeros((10, 30))
        density[3:7, :] = 1.0
        window._result_density = density
        window.export_format.setCurrentIndex(window.export_format.findData("export_svg"))
        window._refresh_export_preview()
        text = window.export_info.text()
        assert "SVG" in text and "60 × 20 mm" in text and "40.0% solid" in text and "outline" in text
        assert window.export_canvas._ax_d.collections                   # the traced outline is drawn
        window.export_format.setCurrentIndex(window.export_format.findData("npy"))
        assert "design.npy" in window.export_info.text() and "outline the file traces" not in window.export_info.text()
    finally:
        window._dirty_timer.stop()
        window.deleteLater()
        app.processEvents()


def test_a_3d_design_shows_as_a_density_cloud_or_its_surface():
    from toporia.apps.gui.canvas import LiveCanvas
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    density = np.zeros((4, 6, 10))
    density[:, 2:4, :] = 1.0
    density[:, 0, 0] = 0.3
    canvas = LiveCanvas()
    canvas.refresh(density, [1.0], 1)
    canvas.show_3d(density, 1.0, cloud=True)
    assert canvas._ax_d.name == "3d" and len(canvas._ax_d.collections) == 1
    points = canvas._ax_d.collections[0]
    assert len(points.get_offsets()) == int((density > 0.05).sum())      # every element with material
    alphas = points.get_facecolor()[:, 3]
    assert alphas.max() > 0.6 > alphas.min()                              # solid opaque, faint material clear
