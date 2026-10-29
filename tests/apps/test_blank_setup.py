"""Blank projects must remain unconfigured drafts until the user makes choices."""

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


@pytest.fixture(autouse=True)
def discard(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.Discard)


def settings(dimension=2, representation="element_density"):
    return dict(dimension=dimension, representation=representation, Lx=20, Ly=10,
                Lz=6 if dimension == 3 else 0, element_size=2, physics="h8" if dimension == 3 else "q4",
                E0=210000, nu=.3, objective="compliance", volfrac=.4)


def test_blank_starts_with_only_an_unselected_dimension(window):
    window.new_blank()
    panel = window.blank_setup
    assert window.workspace_views.currentWidget() is panel
    assert panel.dimension.currentData() is None
    assert panel.representation.currentData() is None
    assert panel.physics.currentData() is None
    assert panel.objective.currentData() is None
    assert panel.groups["representation"].isHidden()
    assert panel.groups["domain"].isHidden()
    assert window.sidebar.isHidden()
    assert not window.run_btn.isEnabled()
    window.go_to_step(2)
    assert window.current_step() == 0
    assert not window._is_dirty()


def test_choices_reveal_only_relevant_sections_and_compatible_representations(window):
    window.new_blank()
    panel = window.blank_setup
    panel.dimension.setCurrentIndex(panel.dimension.findData(3))
    assert not panel.groups["representation"].isHidden()
    assert panel.representation.findData("mmc") == -1
    assert panel.groups["domain"].isHidden()
    panel.representation.setCurrentIndex(panel.representation.findData("element_density"))
    assert not panel.groups["domain"].isHidden()
    assert panel.groups["physics"].isHidden()
    for key, value in {"Lx": 20, "Ly": 10, "Lz": 6, "element_size": 2}.items():
        panel.fields[key].setValue(value)
    assert panel.mesh.text() == "10 × 5 × 3 elements"
    assert not panel.groups["physics"].isHidden()
    assert panel.physics.currentData() is None
    assert panel.physics.findData("q4") == -1
    assert panel.groups["objective"].isHidden()
    assert not panel.create.isEnabled()


def test_dimension_change_requires_fresh_compatible_choices(window):
    window.new_blank()
    panel = window.blank_setup
    panel.load(settings())
    assert panel.create.isEnabled()
    panel.dimension.setCurrentIndex(panel.dimension.findData(3))
    assert panel.representation.currentData() is None
    assert panel.physics.currentData() is None
    assert panel.objective.currentData() is None
    assert not panel.create.isEnabled()


def test_partial_setup_saves_reopens_and_can_be_abandoned(window, tmp_path):
    window.new_blank()
    window.blank_setup.dimension.setCurrentIndex(window.blank_setup.dimension.findData(3))
    window.notes.setPlainText("Spatial fixture")
    assert window._is_dirty()
    path = tmp_path / "draft.top"
    assert window.save_project(path)
    assert not window._is_dirty()
    window._activate_project(Project("Existing", get_run("MBB Beam")))
    assert not window.sidebar.isHidden()
    assert window.open_project(path)
    assert window._blank_pending()
    assert window.blank_setup.dimension.currentData() == 3
    assert window.blank_setup.representation.currentData() is None
    assert window.notes.toPlainText() == "Spatial fixture"
    assert not window._is_dirty()


@pytest.mark.parametrize("dimension,representation,method", [(2, "element_density", "q4+oc"),
    (3, "element_density", "h8+oc"), (2, "mmc", "q4+mma")])
def test_explicit_setup_creates_the_chosen_empty_definition(window, dimension, representation, method):
    window.new_blank()
    window.blank_setup.load(settings(dimension, representation))
    window.blank_setup.create.click()
    assert not window._blank_pending()
    assert window.workspace_views.currentWidget() is window.problem_editor
    assert not window.sidebar.isHidden()
    assert window.run_btn.isEnabled()
    cfg = window.current_config()
    assert (cfg.scenario.Lx, cfg.scenario.Ly, cfg.scenario.Lz) == (20, 10, 6 if dimension == 3 else 0)
    assert cfg.scenario.E0 == 210000
    assert cfg.scenario.nu == .3
    assert cfg.scenario.volfrac == .4
    assert cfg.scenario.regions == []
    assert cfg.solver.method == method
    assert cfg.solver.m == .5
    assert cfg.solver.representation["type"] == representation
    assert window._is_dirty()


def test_unfinished_setup_cannot_run_or_export_solver_defaults(window, tmp_path, monkeypatch):
    window.new_blank()
    notices = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args[2]))
    window.start_execution()
    path = tmp_path / "unfinished.pro"
    assert not window.export_problem(path)
    assert not path.exists()
    assert not window._running
    assert len(notices) == 2


@pytest.mark.parametrize("changes", [{"element_size": .000001}, {"dimension": 3, "Lz": .01}, {"volfrac": .001}])
def test_setup_refuses_values_the_editor_would_silently_clamp(window, changes):
    window.new_blank()
    values = settings(changes.get("dimension", 2)) | changes
    window.blank_setup.load(values)
    assert not window.blank_setup.create.isEnabled()


@pytest.mark.parametrize("state", [[], {"dimension": True}, {"E0": "steel"}, {"nu": 4}, {"unknown": 1}])
def test_invalid_draft_state_is_rejected_before_replacing_the_document(tmp_path, state):
    import json
    data = Project("Bad draft", get_run("MBB Beam"), view={"blank_setup": state}).payload()
    path = tmp_path / "bad.top"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Blank setup"):
        Project.load(path)
