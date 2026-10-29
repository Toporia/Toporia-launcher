"""v0.2.1 navigation, nested edits, persisted views and processed export ownership."""

import base64
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QFileDialog

from toporia.apps.gui.project import Project
from toporia.apps.gui.window import MainWindow
from toporia.framework.problem.workflow import nodes
from toporia.plugins.problems import get_run


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    win._activate_project(Project("v021 test", get_run("MBB Beam").updated(m=.3, max_iter=2)))
    win.show()
    app.processEvents()
    yield win
    win._dirty_timer.stop()
    win.hide()
    win.deleteLater()
    app.processEvents()


def test_sleek_home_and_run_action_only_in_runner(window):
    window.show_home()
    assert window.home.sections.currentIndex() == 0
    assert not window.run_btn.isVisible()
    assert not window.home.search.isVisible()
    window.home.open_section(2)
    assert window.home.explorer.tree.topLevelItemCount() >= 9
    for i in range(5):
        window.go_to_step(i)
        QApplication.processEvents()
        assert window.run_btn.isVisible() == (i == 2)


def test_nested_filter_insert_and_independent_stage_settings_round_trip(window, tmp_path):
    first = window._active_stage
    window.method_view.enter(first + "/filters")
    window._add_function("filter", "heaviside")
    assert window.current_config().solver.filter_specs[-1]["type"] == "heaviside"
    window.method_view.root()
    window._add_function("composition", "parallel")
    tree = window.project.workflow
    second = [n for n in nodes(tree) if n["kind"] == "optimization"][-1]["id"]
    window._select_stage(second)
    window.core._convergence._editors["max_iter"].setValue(7)
    window._select_stage(first)
    assert window.current_config().solver.max_iter == 2
    window._select_stage(second)
    assert window.current_config().solver.max_iter == 7
    window.display_options.controls["volume_graph"].setChecked(True)
    assert window.save_project(tmp_path / "nested.top")
    loaded = Project.load(tmp_path / "nested.top")
    assert loaded.workflow == window.project.workflow
    assert loaded.view["display"]["volume_graph"]
    window._activate_project(loaded)
    assert window._active_stage == second
    assert window.current_config().solver.max_iter == 7


def test_live_disabled_and_interval_do_not_lose_final_result(window):
    window._run_config = window.current_config()
    window._stage_objective_label = "Compliance"
    window.canvas.reset()
    window.display_options.controls["live"].setChecked(False)
    density = np.full((2, 3), .4, dtype="float32")
    packet = {"event": "iteration", "density": base64.b64encode(density.tobytes()).decode(),
              "shape": list(density.shape), "objectives": [2.], "iteration": 1}
    window._worker_message(packet)
    assert window._pending_iteration is None
    assert window.canvas._latest is None
    window.display_options.controls["live"].setChecked(True)
    window.display_options.interval.setValue(3)
    window._worker_message({**packet, "iteration": 2})
    assert window._pending_iteration is None
    window._worker_message({**packet, "iteration": 3})
    window._draw_pending_iteration()
    assert window.canvas._latest[2] == 3
    assert window.run_progress.isHidden()


def test_manual_binary_refresh_exports_the_processed_array(window, tmp_path, monkeypatch):
    from toporia.apps.gui import runner
    window._result_density = np.array([[.1, .49, .5, .9]])
    window._result_config = window.current_config()
    window._result_objective_label = "Compliance"
    window._result_objectives = [12., 10.]
    window._result_iteration = 2
    runner.last_run_folder = tmp_path
    window._apply_binary()
    np.testing.assert_array_equal(window.post_canvas._latest[0], [[0, 0, 1, 1]])
    assert "not re-evaluated" in window.post_canvas.objective_label
    target = tmp_path / "external"
    target.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_: str(target))
    window.export_format.setCurrentIndex(window.export_format.findData("npy"))
    window._write_export()
    np.testing.assert_array_equal(np.load(target / "design.npy"), [[0, 0, 1, 1]])
    runner.last_run_folder = None


def test_dragged_connectors_keep_arrowheads_aligned_with_their_terminal_segment(window):
    window.go_to_step(1)
    blocks = list(window.method_view.blocks.values())
    blocks[0].setPos(-300, 500)
    blocks[1].setPos(600, -200)
    for _, _, edge, _ in window.method_view.edges:
        path = edge.path()
        # Last four elements are left wing, move to tip, right wing; terminal
        # curve reaches the tip before either wing is added.
        count = path.elementCount()
        tip = path.elementAt(count - 2)
        left = path.elementAt(count - 3)
        right = path.elementAt(count - 1)
        assert abs(left.x - tip.x) == pytest.approx(5)
        assert abs(right.x - tip.x) == pytest.approx(5)
        assert tip.y - left.y == pytest.approx(10)
        assert tip.y - right.y == pytest.approx(10)


def test_same_function_can_be_opened_closed_and_reopened_by_clicking(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    window.go_to_step(1)
    window.method_view.enter(window._active_stage)
    window.method_view.fit()
    QApplication.processEvents()
    block = next(b for b in window.method_view.blocks.values() if b.node.kind == "updater")
    point = window.method_view.view.mapFromScene(block.sceneBoundingRect().center())
    for expected in (True, False, True):
        QTest.mouseClick(window.method_view.view.viewport(), Qt.LeftButton, pos=point)
        QApplication.processEvents()
        assert window.parameter_dialog.isVisible() == expected


def test_export_preserves_boolean_removal_of_an_input_fixed_region(window, tmp_path, monkeypatch):
    import struct

    from toporia.apps.gui.geometry import make_object
    from toporia.framework.problem.mesh import make_problem
    from toporia.framework.problem.run import Run
    from toporia.framework.problem.scenario import Scenario

    objects = [make_object("line", (0, 0, 0), (0, 3, 0)),
               make_object(position=(5, 1, 0), role="load"),
               make_object("rectangle", (1, 1, 0), (1, 1, 0), "solid")]
    cfg = Run(scenario=Scenario(Lx=5, Ly=3, regions=objects))
    assert make_problem(cfg.scenario, cfg.solver.m).passive_elements.any()
    # A Boolean difference is allowed to remove an input's mandatory region.
    window._result_config = cfg
    window._result_density = np.zeros((3, 5))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_: str(tmp_path))
    window.export_format.setCurrentIndex(window.export_format.findData("export_stl"))
    window._write_export()
    content = (tmp_path / "post" / "design.stl").read_bytes()
    assert struct.unpack("<I", content[80:84])[0] == 0
    assert len(content) == 84


def test_appearance_switch_preserves_configuration_display_data_and_unapplied_edits(window):
    from PySide6.QtGui import QPalette
    window.canvas.reset()
    density = np.array([[.2, .8], [.6, .4]])
    window.canvas.refresh(density, [4., 3.], 2)
    before = window._capture_project().payload()
    window.problem_editor.fields["x"].setValue(12.3)
    try:
        window.set_appearance("sleek", persist=False)
        app = QApplication.instance()
        assert app.palette().color(QPalette.Window).name() == "#000000"
        assert app.palette().color(QPalette.Text).name() == "#ffffff"
        assert window.method_view.view.backgroundBrush().color().name() == "#000000"
        assert all(block.brush().color().name() == "#000000" for block in window.method_view.blocks.values())
        np.testing.assert_array_equal(window.canvas._latest[0], density)
        assert window.canvas._colours() == ("#000000", "#ffffff", "#ffffff")
        assert window.canvas._im.get_cmap().name == "gray_r"
        assert window._capture_project().payload() == before
        assert window.problem_editor.fields["x"].value() == pytest.approx(12.3)
        assert window.appearance_actions["sleek"].isChecked()
        assert all(button.minimumHeight() >= 140 for button in window.home.section_buttons)
    finally:
        window.set_appearance("basic", persist=False)
    assert QApplication.instance().styleSheet() == ""
    assert window.method_view.view.backgroundBrush().color().lightness() > 128
    assert window._capture_project().payload() == before
    assert window.canvas._im.get_cmap().name == "gray"
    assert window.home.title.palette().color(QPalette.WindowText) == QApplication.instance().palette().color(QPalette.WindowText)
    assert all(button.minimumHeight() >= 140 for button in window.home.section_buttons)


def test_appearance_preference_restores_the_saved_mode(window, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings

    from toporia.apps.gui import appearance
    path = str(tmp_path / "appearance.ini")
    monkeypatch.setattr(appearance, "preference_store", lambda: QSettings(path, QSettings.IniFormat))
    try:
        window.set_appearance("sleek")
        assert QSettings(path, QSettings.IniFormat).value("appearance") == "sleek"
        assert appearance.saved_appearance() == "sleek"
        window.set_appearance("basic", persist=False)
        appearance.apply_appearance(QApplication.instance(), appearance.saved_appearance())
        assert QApplication.instance().property("appearance") == "sleek"
    finally:
        window.set_appearance("basic", persist=False)
