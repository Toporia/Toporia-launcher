"""The Post-process step inspects every run of a session, every field of a run, and every recorded number."""

import contextlib
import io
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from toporia.apps.gui.canvas import LiveCanvas  # noqa: E402
from toporia.apps.gui.inspect_view import InspectPanel, find_runs, variables  # noqa: E402
from toporia.engine.fields import analysis_fields  # noqa: E402
from toporia.engine.loop import run_single  # noqa: E402
from toporia.engine.modes.compare import compare_two  # noqa: E402
from toporia.plugins.problems import get_run  # noqa: E402


def _small(name="MBB Beam", **values):
    return get_run(name).updated(**{"m": 0.4, "max_iter": 4, "tol": 0.0, "save_every": 0, **values})


@pytest.fixture
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_a_single_run_lists_its_fields_and_numbers(app, tmp_path):
    run = _small().with_output_dir(tmp_path)
    with contextlib.redirect_stdout(io.StringIO()):
        density = run_single(run)
    assert np.array_equal(np.load(tmp_path / "final_density.npy"), density)   # every run keeps its field
    panel = InspectPanel(LiveCanvas())
    chosen = []
    panel.selection_changed.connect(lambda d, r, f: chosen.append((d, f)))
    panel.load_session(tmp_path)
    assert [panel.runs.itemText(i) for i in range(panel.runs.count())] == ["This run"]
    assert chosen and chosen[-1][1] == tmp_path
    names = dict(panel.variables_rows) if hasattr(panel, "variables_rows") else {
        panel.table.item(i, 0).text(): panel.table.item(i, 1).text() for i in range(panel.table.rowCount())}
    assert names["Iterations"] == "4" and "objective" in names
    stress = panel.fields.findData("von Mises stress")
    panel.fields.setCurrentIndex(stress)
    assert panel.stack.currentWidget() is panel.field_canvas
    assert panel.fields.currentText() == "von Mises stress"
    assert {"Strain energy", "Displacement"} <= {panel.fields.itemText(i) for i in range(panel.fields.count())}
    panel.add_processed("threshold 0.5", (density >= 0.5).astype(float))
    assert panel.fields.currentText() == "Density · threshold 0.5"
    assert np.array_equal(chosen[-1][0], (density >= 0.5).astype(float))       # export follows the copy


def test_a_comparison_lists_each_of_its_runs(app, tmp_path):
    base = _small().with_output_dir(tmp_path)
    with contextlib.redirect_stdout(io.StringIO()):
        compare_two("volfrac", 0.3, 0.5, base)
    runs = find_runs(tmp_path)
    assert len(runs) == 2
    panel = InspectPanel(LiveCanvas())
    panel.load_session(tmp_path)
    assert panel.runs.count() == 2 and panel.runs.isEnabled()
    panel.runs.setCurrentIndex(1)
    rows = {panel.table.item(i, 0).text() for i in range(panel.table.rowCount())}
    assert "Iterations" in rows and "volume" in rows


def test_the_analysis_fields_follow_each_physics():
    from toporia.framework.problem.mesh import make_problem
    heat = _small("Heat Sink")
    density = np.ones(make_problem(heat.scenario, heat.solver.m).shape)
    fields = analysis_fields(heat, density)
    assert "" in analysis_fields(heat, np.ones((3, 3)))                      # a wrong shape says so
    assert set(fields) == {"Temperature"} and np.nanmax(fields["Temperature"].values) > 0
    mbb = _small()
    elastic = analysis_fields(mbb, np.ones(make_problem(mbb.scenario, mbb.solver.m).shape))
    assert {"von Mises stress", "Strain energy", "Displacement"} <= set(elastic)
    assert elastic["von Mises stress"].unit == "MPa"


def test_variables_read_what_run_json_records():
    record = {"result": {"iterations": 7, "stop_reason": "settled", "feasible": True,
                         "final": {"objective": 1.5, "volume": 0.5},
                         "limits": [{"name": "volume budget", "value": 0.5, "limit": 0.5, "satisfied": True}]},
              "solver": {"definition": {"method": "q4+oc", "m": 1.0}}}
    rows = dict(variables(record))
    assert rows["Iterations"] == 7 and rows["objective"] == 1.5 and rows["Method"] == "q4+oc"
    assert "met" in rows["Limit: volume budget"]
