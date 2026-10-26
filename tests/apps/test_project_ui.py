"""Project lifecycle tests exercise the real forms, study settings and save prompts."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QMessageBox

from toporia.apps.gui.project import Project
from toporia.apps.gui.window import MainWindow
from toporia.plugins.problems import get_run


@pytest.fixture(scope="module")
def window():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    yield window
    window._dirty_timer.stop()
    window.deleteLater()
    app.processEvents()


def test_home_starts_with_library_and_benchmarks_are_protected(window):
    assert window.root_pages.currentWidget() is window.home
    window.open_benchmark("MBB Beam")
    assert window.project.benchmark == "MBB Beam"
    assert not window.core.volume_box.isEnabled()
    assert window.core.isEnabled()
    window.copy_to_custom()
    assert window.project.benchmark is None
    assert window.core.volume_box.isEnabled()
    assert window._is_dirty()


def test_save_reopen_restores_notes_and_study_settings(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.Discard)
    window._activate_project(Project("Experiment", get_run("Cantilever")))
    window.notes.setPlainText("First experiment")
    window.mode.setCurrentText("Sweep")
    window.sg.min_val.setValue(0.23)
    window.sg.max_val.setValue(0.67)
    window.filters.load_specs([{"type": "heaviside", "beta": 4.0}])
    assert window.save_project(tmp_path / "experiment.top")
    expected = window._capture_project().payload()
    window.new_blank()
    assert window.project.objects == []
    assert window.open_project(tmp_path / "experiment.top")
    assert window._capture_project().payload() == expected
    assert not window._is_dirty()
    assert window.notes.toPlainText() == "First experiment"


def test_cancel_keeps_unsaved_project_and_failed_open_keeps_inputs(window, tmp_path, monkeypatch):
    window.notes.setPlainText("Unsaved observation")
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.Cancel)
    previous = window._capture_project().payload()
    window.new_blank()
    assert window._capture_project().payload() == previous
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.Discard)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_: None)
    path = tmp_path / "invalid.top"
    path.write_text("{broken")
    assert not window.open_project(path)
    assert window._capture_project().payload() == previous


def test_problem_export_import_keeps_geometry_independent_of_solver(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.Discard)
    window._activate_project(Project("Experiment", get_run("Drone Arm")))
    path = tmp_path / "arm.pro"
    assert window.export_problem(path)
    scenario = window.current_config().scenario
    assert window.import_problem(path)
    assert window.current_config().scenario == scenario
    assert window.project.benchmark is None


def test_workspace_navigation_and_method_selection_share_actual_controls(window):
    window._activate_project(Project("Experiment", get_run("MBB Beam")))
    window.show_home()
    for index in range(4):
        window.go_to_step(index)
        assert window.root_pages.currentWidget() is window.workspace
        assert window.workspace_views.currentIndex() == index
    window.go_to_step(1)
    node = next(block.node for block in window.method_view.blocks.values() if block.node.kind == "objective")
    original = window.objective.parentWidget()
    window._inspect_method_node(node)
    assert window.current_step() == 1
    assert window.objective.parentWidget() is window.method_inspector
    window.go_to_step(0)
    assert window.objective.parentWidget() is original


def test_filter_reordering_keeps_parameter_references_and_changes_solver_order(window):
    window._activate_project(Project("Experiment", get_run("MBB Beam")))
    window.core.select_method("q4+mma")
    window.filters.load_specs([{"type": "density", "rmin": 2.0}, {"type": "heaviside", "beta": 4.0}])
    window._use_robust_projection()
    window.schedules.load_specs([{"type": "steps", "path": "filters[1].beta", "start": 1., "end": 4., "step": 1., "every": 5}])
    window.filters.move_row(1, -1)
    cfg = window.current_config()
    assert [spec["type"] for spec in cfg.solver.filter_specs] == ["heaviside", "density"]
    assert cfg.solver.filter_specs[0]["beta"] == 4.0
    assert cfg.solver.filter_specs[1]["rmin"] == 2.0
    assert cfg.solver.schedules[0]["path"] == "filters[0].beta"
    assert cfg.solver.variants["path"] == "filters[0].eta"
    before = window._capture_project().payload()
    block = next(iter(window.method_view.blocks.values()))
    block.setPos(42, 64)
    assert window.current_config() == cfg
    assert window._capture_project().payload() != before


def test_real_qt_worker_completes_without_blocking_setup_or_overwriting_runs(window, tmp_path, monkeypatch):
    import time

    from toporia.apps.gui import runner
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.Discard)
    run = get_run("MBB Beam").updated(m=.3, max_iter=2, save_every=0)
    window._activate_project(Project("Async experiment", run))
    assert window.save_project(tmp_path / "project.top")
    folders = []
    for _ in range(2):
        window._on_run()
        assert window._running
        assert not window._pages.isEnabled()
        assert window.current_step() == 2
        folders.append(window._run_folder)
        deadline = time.monotonic() + 40
        while window._running and time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(.01)
        assert not window._running
        assert window.run_status.text().startswith("Finished"), window.log.toPlainText()
        assert window._pages.isEnabled()
        assert window.export_btn.isEnabled()
        assert runner.last_run_folder == folders[-1]
        assert (folders[-1] / "input.top").exists()
        assert (folders[-1] / "run.json").exists()
    assert folders[0] != folders[1]
    assert window.run_history.count() == 2
