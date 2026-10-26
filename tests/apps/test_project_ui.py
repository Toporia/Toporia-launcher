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
