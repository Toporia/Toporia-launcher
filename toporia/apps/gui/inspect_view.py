# apps/gui/inspect_view.py — the Post-process step's inspector: every run, every field, every number.
#
# A finished session is one run, or many (a sweep or a comparison writes one folder per
# run).  The inspector lists them; for the chosen run it shows the density, the copies
# post-processing made of it, and the finite-element fields of the final design (stress,
# strain energy, displacement, temperature: engine/fields.py), computed when first asked
# for.  Beside the picture is every number run.json records.  The chosen run is what
# post-processing and export then act on.

import json
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .canvas import PanZoom

DENSITY = "Density"


def _load_run(folder):
    """(Run, density, record) of a finished run folder; raises OSError/ValueError/KeyError."""
    from toporia.framework.problem.files import from_dict
    from toporia.framework.problem.run import Run
    from toporia.framework.problem.scenario import Scenario
    from toporia.framework.problem.solver import Solver
    record = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    run = Run(scenario=from_dict(Scenario, record["scenario"]["definition"]),
              solver=from_dict(Solver, record["solver"]["definition"]))
    for name in ("final_density.npy", "design.npy"):
        if (folder / name).exists():
            return run, np.load(folder / name, allow_pickle=False), record
    raise ValueError(f"{folder} has no saved design")


def find_runs(session):
    """Every finished run in a session folder: the folder itself first, then its run sub-folders."""
    session = Path(session)
    found = [session] if (session / "run.json").exists() else []
    found += sorted(p.parent for p in session.rglob("run.json") if p.parent != session)
    return found


def variables(record):
    """(name, value) rows of what a run.json records about its result."""
    result = record.get("result", {})
    rows = [("Iterations", result.get("iterations")), ("Stopped", result.get("stop_reason")),
            ("Feasible", result.get("feasible"))]
    rows += [(name, value) for name, value in result.get("final", {}).items()]
    for limit in result.get("limits", []):
        state = "met" if limit.get("satisfied") else "NOT met"
        rows.append((f"Limit: {limit.get('name')}", f"{limit.get('value'):.4g} ≤ {limit.get('limit'):.4g} ({state})"
                     if isinstance(limit.get("value"), float) and isinstance(limit.get("limit"), float) else state))
    solver = record.get("solver", {}).get("definition", {})
    rows += [("Method", solver.get("method")), ("Elements per mm", solver.get("m"))]
    return [(name, value) for name, value in rows if value is not None]


class FieldCanvas(PanZoom, FigureCanvas):
    """One field in colour with its scale; wheel zooms, drag pans, double-click shows it all."""

    def __init__(self, parent=None):
        self._fig = Figure(figsize=(8, 4))
        super().__init__(self._fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._install_pan_zoom()

    def show_field(self, values, title, unit, element_size=1.0, cmap="viridis"):
        from .appearance import colours
        colors = colours(QApplication.instance())
        bg, tc = colors["background"].name(), colors["text"].name()
        values = np.asarray(values, dtype=float)
        if values.ndim == 3:                               # (z, y, x): what the depth holds at most
            with np.errstate(all="ignore"):
                values = np.nanmax(values, axis=0) if np.isfinite(values).any() else values[0]
            title += "  (largest through the depth)"
        self._fig.clf()
        self._fig.patch.set_facecolor(bg)
        ax = self._fig.add_subplot(1, 1, 1)
        ax.set_facecolor(bg)
        ny, nx = values.shape
        image = ax.imshow(np.flipud(values), cmap=cmap, interpolation="nearest", aspect="equal",
                          extent=[0, nx * element_size, 0, ny * element_size])
        bar = self._fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
        bar.set_label(unit, color=tc)
        bar.ax.tick_params(colors=tc)
        ax.set_title(title, color=tc, fontsize=10)
        ax.set_xlabel("x (mm)", color=tc, fontsize=9)
        ax.set_ylabel("y (mm)", color=tc, fontsize=9)
        ax.tick_params(colors=tc)
        self._fig.tight_layout(pad=1.0)
        self.draw_idle()


class InspectPanel(QWidget):
    """Choose a run of the session and a field of it; see the picture and every recorded number."""

    #: (density, Run, run folder) of the run and density-like field now chosen.
    selection_changed = Signal(object, object, object)

    def __init__(self, density_canvas, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel("Run"))
        self.runs = QComboBox()
        self.runs.setToolTip("Every run of the shown session: one, or each run of a sweep or comparison.")
        self.runs.setMinimumContentsLength(24)
        row.addWidget(self.runs, 1)
        row.addSpacing(12)
        row.addWidget(QLabel("Field"))
        self.fields = QComboBox()
        self.fields.setToolTip("The design, the copies post-processing made of it, and the finite-element "
                               "fields of the final design (computed when first chosen).")
        self.fields.setMinimumContentsLength(22)
        row.addWidget(self.fields, 1)
        self.toolbar = row
        layout.addLayout(row)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        body = QHBoxLayout()
        self.stack = QStackedWidget()
        self.density_canvas = density_canvas
        self.field_canvas = FieldCanvas()
        self.stack.addWidget(density_canvas)
        self.stack.addWidget(self.field_canvas)
        body.addWidget(self.stack, 1)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Variable", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFixedWidth(320)
        body.addWidget(self.table)
        layout.addLayout(body, 1)
        self._runs = []          # [{"folder", "label", "run", "density", "record", "fields": {name: (kind, value)}}]
        self.runs.currentIndexChanged.connect(lambda *_: self._run_chosen())
        self.fields.currentIndexChanged.connect(lambda *_: self._field_chosen())

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_session(self, session, main=None):
        """List the session's runs; `main` is the (Run, density) the window already shows, if any."""
        self._runs = []
        folders = find_runs(session) if session is not None else []
        for folder in folders:
            label = "This run" if folder == Path(session) else folder.relative_to(session).as_posix()
            self._runs.append({"folder": folder, "label": label, "run": None, "density": None,
                               "record": None, "fields": {}})
        if main is not None:
            if not self._runs:
                self._runs.append({"folder": session, "label": "This run", "run": None, "density": None,
                                   "record": None, "fields": {}})
            self._runs[0]["run"], self._runs[0]["density"] = main
        blocked = self.runs.blockSignals(True)
        self.runs.clear()
        for entry in self._runs:
            self.runs.addItem(entry["label"])
        self.runs.blockSignals(blocked)
        self.runs.setEnabled(len(self._runs) > 1)
        if self._runs:
            self.runs.setCurrentIndex(0)
            self._run_chosen(main_shown=main is not None)
        else:
            self.fields.clear()
            self.table.setRowCount(0)
            self.note.setText("No finished run to inspect yet.")

    def current(self):
        index = self.runs.currentIndex()
        return self._runs[index] if 0 <= index < len(self._runs) else None

    def add_processed(self, label, density):
        """A post-processed copy of the chosen run's design: a new field, chosen at once."""
        entry = self.current()
        if entry is None:
            return
        name = f"{DENSITY} · {label}"
        entry["fields"][name] = ("density", np.asarray(density, dtype=float).copy())
        self._fill_fields(entry, select=name)

    # ── Choosing ──────────────────────────────────────────────────────────────

    def _run_chosen(self, main_shown=False):
        entry = self.current()
        if entry is None:
            return
        if entry["run"] is None or entry["record"] is None:
            try:
                run, density, record = _load_run(entry["folder"])
                entry["record"] = record
                if entry["run"] is None:
                    entry["run"], entry["density"] = run, density
            except (OSError, ValueError, KeyError) as error:
                self.note.setText(f"Cannot read this run: {error}")
                return
        entry["fields"].setdefault(DENSITY, ("density", entry["density"]))
        self._fill_table(entry["record"])
        self._fill_fields(entry, select=DENSITY, redraw=not main_shown)

    def _fill_fields(self, entry, select=None, redraw=True):
        blocked = self.fields.blockSignals(True)
        self.fields.clear()
        for name in entry["fields"]:
            self.fields.addItem(name)
        for name in ("von Mises stress", "Strain energy", "Displacement", "Temperature"):
            if name not in entry["fields"] and not entry.get("analysed"):
                self.fields.addItem(name + "  (computed when chosen)", name)
        self.fields.setCurrentIndex(max(0, self.fields.findText(select)) if select else 0)
        self.fields.blockSignals(blocked)
        if redraw:
            self._field_chosen()

    def _fill_table(self, record):
        rows = variables(record or {})
        self.table.setRowCount(len(rows))
        for i, (name, value) in enumerate(rows):
            shown = f"{value:.6g}" if isinstance(value, float) else str(value)
            for col, text in enumerate((str(name), shown)):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(i, col, item)

    def _field_chosen(self):
        entry = self.current()
        if entry is None or self.fields.currentIndex() < 0:
            return
        name = self.fields.currentData() or self.fields.currentText()
        if name not in entry["fields"]:
            self._analyse(entry)
            if name not in entry["fields"]:
                self.note.setText(f"{name} is not available for this run's physics.")
                self._fill_fields(entry, select=DENSITY)
                return
            self._fill_fields(entry, select=name, redraw=False)
        kind, value = entry["fields"][name]
        h = 1 / entry["run"].solver.m
        if kind == "density":
            self.note.setText("" if name == DENSITY else "A post-processed copy; the objective was not re-evaluated.")
            if name == DENSITY and entry is self._runs[0] and self.density_canvas._latest is not None:
                self.stack.setCurrentWidget(self.density_canvas)    # the run's own view, with its history
            else:
                self.field_canvas.show_field(value, f"{entry['label']} · {name}", "density", h, cmap="gray_r")
                self.stack.setCurrentWidget(self.field_canvas)
            self.selection_changed.emit(value, entry["run"], entry["folder"])
            return
        cmap = {"Temperature": "inferno", "von Mises stress": "turbo"}.get(name, "viridis")
        self.note.setText(value.note)
        self.field_canvas.show_field(value.values, f"{entry['label']} · {name}", value.unit, h, cmap=cmap)
        self.stack.setCurrentWidget(self.field_canvas)

    def _analyse(self, entry):
        """Solve the run's physics once for its design; keep every field it gives."""
        from toporia.engine.fields import analysis_fields
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            fields = analysis_fields(entry["run"], entry["fields"][DENSITY][1])
        finally:
            QApplication.restoreOverrideCursor()
        entry["analysed"] = True
        if "" in fields:
            self.note.setText(fields.pop("").note)
        for name, field in fields.items():
            entry["fields"][name] = ("analysis", field)
