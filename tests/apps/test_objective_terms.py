"""test_objective_terms.py — the combined objective in the GUI (To do item 4).

Choosing "Combined objective" shows the terms; what is typed there reaches the run,
survives a save and a reload, and a bad formula is reported before a run.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from toporia_core.framework.registries import OBJECTIVE_ROLE, resolve_response  # noqa: E402

SPEC = {"type": "combined", "combine": "expression", "ks_p": 40.0,
        "expression": "c * sqrt(peak_stress)",
        "terms": [{"type": "compliance", "weight": 1.0, "name": "c"},
                  {"type": "peak_stress", "p": 6.0, "weight": 0.5, "sense": "max"}]}


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_terms_editor_round_trips_a_combined_objective(app):
    from toporia_gui.panels.specs import ObjectiveGroup
    from toporia_library.responses import responses_for
    group = ObjectiveGroup(responses_for(OBJECTIVE_ROLE))
    assert group.terms.isHidden()                    # only for a combined objective
    group.load_spec(SPEC)
    assert not group.terms.isHidden() and not group.terms.expression.isHidden()
    assert group.get_spec() == SPEC
    resolve_response(group.get_spec(), OBJECTIVE_ROLE)   # what the GUI makes is a valid spec

    group.terms.expression.setText("c * missing")
    assert "not a variable here" in group.terms.status.text()
    group.load_spec({**SPEC, "combine": "sum"})
    assert group.terms.expression.isHidden() and "expression" not in group.get_spec()

    group.set_allowed(["compliance", "volume", "combined"])     # e.g. a physics without stress
    assert "peak_stress is not available" in group.terms.status.text()


def test_a_combined_objective_reaches_the_run_and_the_saved_project(app, tmp_path, monkeypatch):
    from toporia_gui.window import MainWindow
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", lambda *_: QtWidgets.QMessageBox.Discard)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *_: None)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *_: None)
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda *_: QtWidgets.QMessageBox.Ok)
    window = MainWindow()
    window.open_benchmark("MBB Beam")
    window.copy_to_custom()
    window.core.select_method("q4+mma")
    window.objective.load_spec(SPEC)
    assert window.current_config().scenario.objective == SPEC

    path = tmp_path / "combined.top"
    assert window.save_project(path)
    window.objective.load_spec({"type": "compliance"})
    assert window.open_project(path)
    assert window.current_config().scenario.objective == SPEC
    window.close()
