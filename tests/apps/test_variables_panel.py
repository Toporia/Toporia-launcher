"""test_variables_panel.py — the Problem page's variable space (To do items 1 + 2).

The panel lists what the physics computes and the fields of a design, holds your own
variables, offers them to the objective and constraints, and saves them with the project.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

VARIABLES = [{"name": "s", "type": "peak_stress", "p": 6.0},
             {"name": "ratio", "expression": "compliance * s / volume"}]


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_panel_lists_the_variable_space_of_the_physics(app):
    from toporia_gui.panels.variables import VariablesGroup
    from toporia_library.models.q4 import Q4Model
    from toporia_library.models.q4_heat import Q4HeatModel
    panel = VariablesGroup()
    panel.set_physics(Q4Model.physics)
    assert "compliance" in panel.builtin.text() and "peak_stress" in panel.builtin.text()
    assert "von Mises stress" in panel.fields.text() and "temperature" not in panel.fields.text()
    panel.load_specs(VARIABLES)
    assert panel.get_specs() == VARIABLES and panel.status.text() == ""
    assert {"compliance", "volume", "s", "ratio"} <= set(panel.names())

    panel.load_specs([*VARIABLES, {"name": "loop", "expression": "loop + 1"}])
    assert "circle" in panel.status.text()
    panel.set_physics(Q4HeatModel.physics)
    assert "temperature" in panel.fields.text() and "thermal_compliance" in panel.builtin.text()


def test_variables_reach_the_run_the_objective_and_the_saved_project(app, tmp_path, monkeypatch):
    from toporia_gui.window import MainWindow
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", lambda *_: QtWidgets.QMessageBox.Discard)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *_: None)
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda *_: QtWidgets.QMessageBox.Ok)
    window = MainWindow()
    window.open_benchmark("MBB Beam")
    window.copy_to_custom()
    window.core.select_method("q4+conlin")
    window.variables.load_specs(VARIABLES)
    window.objective.load_spec({"type": "variable", "variable": "ratio"})
    window.constraints.load_specs([{"type": "variable", "variable": "s", "limit": 50.0, "bound": "at_most"}])
    cfg = window.current_config()
    assert cfg.scenario.variables == VARIABLES
    assert cfg.scenario.objective == {"type": "variable", "variable": "ratio", "limit": 1.0, "bound": "at_most"}
    assert cfg.scenario.constraints[-1]["variable"] == "s"
    assert window.objective._row._variable.findText("ratio") >= 0      # offered by name

    path = tmp_path / "variables.top"
    assert window.save_project(path)
    window.variables.load_specs([])
    assert window.open_project(path)
    assert window.current_config().scenario.variables == VARIABLES
    window.close()


def test_an_extra_physics_offers_its_quantities_to_your_variables(app, tmp_path, monkeypatch):
    from toporia_gui.window import MainWindow
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", lambda *_: QtWidgets.QMessageBox.Discard)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *_: None)
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda *_: QtWidgets.QMessageBox.Ok)
    window = MainWindow()
    window.open_benchmark("MBB Beam (Stiffness and Heat)")
    window.copy_to_custom()
    assert window.extra_physics.get_specs() == [{"model": "q4_heat", "interpolation": {"type": "simp", "penal": 1.0}}]
    row = window.variables._rows[0]
    assert row.quantity.findData("q4_heat:thermal_compliance") >= 0
    assert "on 2-D Q4 heat" in row.quantity.currentText()
    cfg = window.current_config()
    assert cfg.scenario.variables == [{"name": "heat", "type": "thermal_compliance", "physics": "q4_heat"}]
    assert cfg.scenario.extra_physics[0]["model"] == "q4_heat"

    window.extra_physics._rows[0].Emin.setText("0.01")
    assert window.current_config().scenario.extra_physics[0]["Emin"] == 0.01
    window.extra_physics.load_specs([{"model": "q4_heat"}, {"model": "q4_heat"}])
    assert "named twice" in window.extra_physics.status.text()
    window.close()
