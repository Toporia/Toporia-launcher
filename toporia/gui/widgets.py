# widgets.py — all parameter-editor UI components
#
# This file contains only Qt widgets.  There is no optimisation logic here.
#
# Method, filter and scenario inputs are not written by hand.  Each panel is a
# ParamForm (gui/param_form.py) generated from the Param declarations on the
# plugin classes and in core/scenario.py and core/solver.py, so adding a method, a filter or a
# parameter needs no change in this file.
#
# Widget hierarchy (what contains what):
#   MainWindow
#     └─ left panel
#          ├─ PipelineView         (the selected chain, stage by stage, and why parts are missing)
#          ├─ CoreParamsGroup      (scenario fields; method as physics model + updater, or whole)
#          ├─ ObjectiveGroup       (what to minimise, as the method allows)
#          ├─ SpecListGroup        constraints (hidden when the method enforces none)
#          ├─ SpecListGroup        filters (hidden when the method takes no filters)
#          ├─ LoadCasesGroup       (one LoadCaseRow per force)
#          └─ one group per analysis mode (sweep, compare, sensitivity, ...)

import html

from PySide6.QtCore import Qt, Signal  # Qt signal/slot system (see python_primer.py §11)
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .param_form import ParamForm

# Extra items added to the sweep dropdown in sensitivity-sweep modes
_SENS_SWEEP_EXTRA = [
    ("Sensitivity base value", "sens.base_value"),
    ("Sensitivity gap",        "sens.gap"),
]


# ── Spinbox factory helpers ───────────────────────────────────────────────────
# These avoid writing the same five lines every time a numeric input is needed.

def _dbl(v, lo, hi, dec=3, step=0.1):
    """Create a floating-point spinbox with the given initial value, range, and step."""
    s = QDoubleSpinBox()
    s.setRange(lo, hi); s.setValue(v); s.setDecimals(dec); s.setSingleStep(step)
    return s

def _int(v, lo, hi):
    """Create an integer spinbox."""
    s = QSpinBox(); s.setRange(lo, hi); s.setValue(v); return s


def _add_tooltip_row(form, label, widget, tooltip):
    """Add a form row where both the label and editor explain the parameter."""
    lbl = QLabel(label)
    lbl.setToolTip(tooltip)
    widget.setToolTip(tooltip)
    form.addRow(lbl, widget)


class _CollapsibleSection(QWidget):
    """Small reusable dropdown section used by the left-side controls."""

    def __init__(self, title, parent=None, expanded=False):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 4)
        outer.setSpacing(0)

        self._title = title
        self._toggle = QPushButton()
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._toggle.toggled.connect(self._on_toggle)
        outer.addWidget(self._toggle)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(4, 4, 4, 4)
        self.body_layout.setSpacing(2)
        outer.addWidget(self.body)

        self._on_toggle(expanded)

    def _on_toggle(self, checked):
        self.body.setVisible(checked)
        self._toggle.setText(f"{'▼' if checked else '▶'}  {self._title}")

    def set_title(self, title):
        self._title = title
        self._on_toggle(self._toggle.isChecked())


# ── Sweep dropdown helpers ────────────────────────────────────────────────────

def _fill_combo(combo, items, prefer=""):
    """Rebuild a parameter dropdown from (label, parameter_path) pairs.

    The path is stored as the item's data and is what apply_param() receives;
    the items come from toporia.library.catalog.parameter_paths.  The previous
    selection is kept when it still exists, otherwise `prefer`, otherwise the first.
    """
    cur = combo.currentData() or prefer
    combo.blockSignals(True); combo.clear()
    for label, path in items:
        combo.addItem(label, userData=path)
    idx = combo.findData(cur); combo.setCurrentIndex(max(idx, 0))
    combo.blockSignals(False)


def _fill_sens_sweep_combo(combo, items, prefer=""):
    """Like _fill_combo but appends the two sensitivity-specific sweep targets."""
    _fill_combo(combo, list(items) + _SENS_SWEEP_EXTRA, prefer)


# ── Load case widgets ─────────────────────────────────────────────────────────

class LoadCaseRow(QWidget):
    """One horizontal row representing a single load case.

    Contains: numbered label | Fmag spinbox | Angle spinbox | Weight spinbox | ✕ button
    """
    def __init__(self, n, fmag=1.0, fa=0.0, weight=1.0, on_remove=None, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self); row.setContentsMargins(0, 2, 0, 2)

        self._lbl = QLabel(f"<b>LC {n}</b>"); self._lbl.setFixedWidth(36)  # bold HTML label
        row.addWidget(self._lbl)

        self.fmag   = _dbl(fmag,   0, 1e6, dec=1)              # force magnitude spinbox
        self.fa     = _dbl(fa,  -360, 360, dec=1, step=15.0)   # angle in degrees
        self.weight = _dbl(weight, 0,   1, dec=1, step=0.1)    # compliance weight (should sum to 1)

        for w in (self.fmag, self.fa, self.weight):
            w.setFixedWidth(72)

        for lbl, w, tip in [("Fmag",   self.fmag,   "Force magnitude"),
                             ("Angle°", self.fa,     "0=+x  90=+y  270=-y"),
                             ("Weight", self.weight, "Compliance weight")]:
            l = QLabel(lbl); l.setToolTip(tip)   # tooltip appears on mouse hover
            w.setToolTip(tip)
            row.addWidget(l); row.addWidget(w)

        # The ✕ button calls on_remove(self) — passing *this row* as the argument
        # so the parent LoadCasesGroup knows which row to delete.
        btn = QPushButton("✕"); btn.setFixedWidth(28); btn.setToolTip("Remove load case")
        btn.clicked.connect(lambda: on_remove(self) if on_remove else None)
        row.addWidget(btn)

    def set_number(self, n):
        """Update the LC label after rows are added or removed."""
        self._lbl.setText(f"<b>LC {n}</b>")

    def get(self):
        """Read spinbox values and return a LoadCase dataclass instance."""
        from toporia.core import LoadCase
        return LoadCase(Fmag=self.fmag.value(), Fa=self.fa.value(), weight=self.weight.value())


class LoadCasesGroup(QWidget):
    """A titled box containing a variable number of LoadCaseRow widgets.

    Emits cases_changed(n) whenever a row is added or removed so the sweep
    parameter dropdowns can update their load-case entries.
    """
    cases_changed = Signal(int)   # Signal declaration — fires with the new row count

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._section = _CollapsibleSection("Load Cases", expanded=False)
        outer.addWidget(self._section)

        self._vbox = self._section.body_layout
        self._rows = []
        self._add(1.0, 0.0, 0.5)    # default: two load cases matching the example scripts
        self._add(1.0, 270.0, 0.5)
        btn = QPushButton("+ Add load case")
        btn.clicked.connect(lambda: self._add()); self._vbox.addWidget(btn)

    def _add(self, fmag=1.0, fa=0.0, weight=1.0):
        row = LoadCaseRow(len(self._rows) + 1, fmag, fa, weight, on_remove=self._remove)
        self._rows.append(row)
        # insertWidget places the row BEFORE the "Add" button (last widget in the layout).
        self._vbox.insertWidget(len(self._rows) - 1, row)
        self.cases_changed.emit(len(self._rows))   # notify sweep dropdowns

    def _remove(self, row):
        if len(self._rows) <= 1: return   # always keep at least one load case
        self._rows.remove(row); self._vbox.removeWidget(row); row.deleteLater()
        for i, r in enumerate(self._rows): r.set_number(i + 1)  # renumber remaining rows
        self.cases_changed.emit(len(self._rows))

    def get_load_cases(self):
        return [r.get() for r in self._rows]   # list comprehension: call .get() on every row

    def setTitle(self, title):
        """Compatibility with the old QGroupBox-based LoadCasesGroup."""
        self._section.set_title(title)

    def load_from_config(self, cfg):
        """Replace all rows with the load cases from a Run."""
        for row in list(self._rows):
            self._vbox.removeWidget(row)
            row.hide()          # disappear now; Qt frees it on the next event-loop pass
            row.deleteLater()
        self._rows.clear()
        for lc in cfg.scenario.load_cases:
            self._add(lc.Fmag, lc.Fa, lc.weight)


# ── Core and sweep parameter groups ──────────────────────────────────────────

class CoreParamsGroup(QWidget):
    """Scenario fields, the optimisation method as explicit parts, and convergence/output.

    The method is chosen part by part: a physics model and an updater, any
    pair of them — or a whole method that does not split into parts (the RBF
    level set).  Each part shows its own parameters.  Every input is generated
    from Param declarations and the plugin registries, so a new model, updater
    or method appears here without editing this file.
    """
    method_changed = Signal(str)   # fires with the method name: "<model>+<updater>" or a whole method

    #: The "Method" selector's entry for a method assembled from a model and an updater.
    PARTS = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        from toporia.core import OUTPUT_PARAMS, SCENARIO_PARAMS, SOLVER_PARAMS
        from toporia.core.params import select
        from toporia.library.methods import METHODS
        from toporia.library.models import MODELS
        from toporia.library.updaters import UPDATERS

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        core = QGroupBox("Core Parameters")
        self._design = ParamForm(select(SOLVER_PARAMS + SCENARIO_PARAMS, "m", "volfrac"))
        QVBoxLayout(core).addWidget(self._design)
        outer.addWidget(core)

        opt = _CollapsibleSection("Method", expanded=True)
        selector = QFormLayout()
        self.approach = QComboBox()
        self.approach.addItem("Physics model + updater", userData=self.PARTS)
        for cls in METHODS.classes():
            self.approach.addItem(f"{cls.label} (whole method)", userData=cls.name)
        _add_tooltip_row(selector, "Method", self.approach,
                         "Pick a physics model and an updater separately (any pair works), or a whole "
                         "method that brings its own design representation and update.")
        opt.body_layout.addLayout(selector)

        # One selector and one parameter panel per part; whole methods get a panel each.
        self.model, self._model_forms, self._model_row = self._part_selector(
            opt, "Physics model", MODELS.classes(),
            "What is solved: the physics engine, and with it which objectives and constraints "
            "can be computed.")
        self.updater, self._updater_forms, self._updater_row = self._part_selector(
            opt, "Updater", UPDATERS.classes(),
            "How the design moves from one iteration to the next.")
        self._method_forms = {}
        for cls in METHODS.classes():
            form = ParamForm(cls.params)
            self._method_forms[cls.name] = form
            opt.body_layout.addWidget(form)
        outer.addWidget(opt)

        self._convergence = ParamForm(select(SOLVER_PARAMS, "max_iter", "tol"))
        self._output = ParamForm(OUTPUT_PARAMS)
        for title, form in (("Convergence", self._convergence), ("Output", self._output)):
            section = _CollapsibleSection(title, expanded=False)
            section.body_layout.addWidget(form)
            outer.addWidget(section)

        for combo in (self.approach, self.model, self.updater):
            combo.currentIndexChanged.connect(self._on_method_changed)
        self._on_method_changed()

    @staticmethod
    def _part_selector(section, title, classes, tooltip):
        """A titled selector for one part, with that part's parameter panel under it."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        row = QFormLayout()
        combo = QComboBox()
        _add_tooltip_row(row, title, combo, tooltip)
        layout.addLayout(row)
        forms = {}
        for cls in classes:
            combo.addItem(cls.label, userData=cls.name)
            forms[cls.name] = ParamForm(cls.params)
            layout.addWidget(forms[cls.name])
        section.body_layout.addWidget(box)
        return combo, forms, box

    def _composed(self):
        return self.approach.currentData() == self.PARTS

    def method_name(self):
        """The selected method: "<model>+<updater>", or a whole method's name."""
        from toporia.core.composition import SEPARATOR
        if self._composed():
            return f"{self.model.currentData()}{SEPARATOR}{self.updater.currentData()}"
        return self.approach.currentData()

    def select_method(self, name):
        """Show the method `name`, in either form; older names such as "density" are accepted."""
        from toporia.core.composition import ComposedMethod
        from toporia.library.methods import method_class
        cls = method_class(name)
        combos = (self.approach, self.model, self.updater)
        for combo in combos:
            combo.blockSignals(True)
        if issubclass(cls, ComposedMethod):
            self.approach.setCurrentIndex(self.approach.findData(self.PARTS))
            self.model.setCurrentIndex(self.model.findData(cls.model.name))
            self.updater.setCurrentIndex(self.updater.findData(cls.updater.name))
        else:
            self.approach.setCurrentIndex(self.approach.findData(cls.name))
        for combo in combos:
            combo.blockSignals(False)
        self._on_method_changed()

    def _all_forms(self):
        return [*self._model_forms.values(), *self._updater_forms.values(), *self._method_forms.values()]

    def _visible_forms(self):
        if self._composed():
            return [self._model_forms[self.model.currentData()], self._updater_forms[self.updater.currentData()]]
        return [self._method_forms[self.approach.currentData()]]

    def _on_method_changed(self, *_):
        composed = self._composed()
        self._model_row.setVisible(composed)
        self._updater_row.setVisible(composed)
        visible = self._visible_forms()
        for form in self._all_forms():
            form.setVisible(form in visible)
        self.method_changed.emit(self.method_name())

    def get_kwargs(self):
        """Return {field: value} to overlay on a Run with Run.updated."""
        method_params = {}
        for form in self._visible_forms():
            method_params.update(form.get_values())
        return {
            **self._design.get_values(),
            **self._convergence.get_values(),
            **self._output.get_values(),
            "method": self.method_name(),
            "method_params": method_params,
        }

    def load_from_config(self, cfg):
        """Populate every panel from a Run (called when a preset is selected)."""
        from toporia.core import read_param
        self.select_method(cfg.solver.method)
        visible = self._visible_forms()
        for form in self._all_forms():
            mine = {k: v for k, v in cfg.solver.method_params.items() if k in form.names()}
            form.set_values(mine if form in visible else {})
        for form in (self._design, self._convergence, self._output):
            form.set_values({key: read_param(cfg, key) for key in form.names()})


class PipelineView(QGroupBox):
    """The selected pipeline, stage by stage, and why any part of it is unavailable.

    It shows what the run will actually do (which filters, which physics,
    which responses, which updater), so swapping one part is visible at once,
    and a hidden panel (no filters, no constraints) is explained, not just gone.
    """

    def __init__(self, parent=None):
        super().__init__("Pipeline", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self._stages = QLabel()
        self._stages.setWordWrap(True)
        self._stages.setTextFormat(Qt.RichText)
        self._notes = QLabel()
        self._notes.setWordWrap(True)
        self._notes.setTextFormat(Qt.RichText)
        layout.addWidget(self._stages)
        layout.addWidget(self._notes)
        self._plain_stages, self._plain_notes = [], []

    def show_pipeline(self, stages, notes):
        """Show [(stage, text), ...] top to bottom, then the notes in grey."""
        self._plain_stages, self._plain_notes = list(stages), list(notes)
        rows = [f"<b>{html.escape(stage)}</b>: {html.escape(text)}" for stage, text in stages]
        self._stages.setText("<br>&nbsp;&nbsp;↓ ".join(rows) + "<br>&nbsp;&nbsp;↺ <i>next design</i>")
        self._notes.setVisible(bool(notes))
        self._notes.setText("<br>".join(f"<span style='color:gray'>• {html.escape(n)}</span>" for n in notes))

    def stages(self):
        """The displayed [(stage, text), ...]."""
        return list(self._plain_stages)

    def notes(self):
        """The displayed notes."""
        return list(self._plain_notes)


class CompareLoadCasesParamsGroup(QGroupBox):
    """Two independent load-case sets for a head-to-head structural comparison.

    Both sets share all Core Parameters (volfrac, mesh, material, …).
    Each set has its own Fmag / Angle / Weight rows and its own +Add button,
    exactly like the main Load Cases group.

    The global Load Cases panel is hidden while this mode is active so the
    screen is uncluttered.
    """
    def __init__(self, parent=None):
        super().__init__("Compare Load Cases", parent)
        v = QVBoxLayout(self)
        v.setSpacing(6)

        self.lc_a = LoadCasesGroup()
        self.lc_a.setTitle("Load Cases — Design A")
        v.addWidget(self.lc_a)

        self.lc_b = LoadCasesGroup()
        self.lc_b.setTitle("Load Cases — Design B")
        v.addWidget(self.lc_b)

    def get_load_cases_a(self): return self.lc_a.get_load_cases()
    def get_load_cases_b(self): return self.lc_b.get_load_cases()


class SensitivityParamsGroup(QGroupBox):
    """Settings for a sensitivity field analysis (visible only in Sensitivity mode).

    Runs two optimisations at `base_value` and `base_value + gap`, then shows
    the per-element finite-difference sensitivity as a blue–white–red overlay.
    """
    def __init__(self, parent=None):
        super().__init__("Sensitivity Parameters", parent)
        f = QFormLayout(self)
        self.param      = QComboBox()
        self.base_value = _dbl(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap        = _dbl(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Parameter",  self.param),
                       ("Base value", self.base_value),
                       ("Gap (Δ)",    self.gap)]:
            f.addRow(lbl, w)

    def refresh(self, items): _fill_combo(self.param, items, prefer="volfrac")
    def key(self): return self.param.currentData() or self.param.currentText()


class CompareTwoParamsGroup(QGroupBox):
    """Settings for a two-run comparison (visible only in Compare Two mode).

    The user picks one parameter to vary, sets two values (A and B), and
    optionally adjusts the density threshold used to classify solid vs void.
    """
    def __init__(self, parent=None):
        super().__init__("Compare Two Parameters", parent)
        f = QFormLayout(self)
        self.param   = QComboBox()
        self.value_a = _dbl(0.20, -1e6, 1e6, dec=4, step=0.05)
        self.value_b = _dbl(0.40, -1e6, 1e6, dec=4, step=0.05)
        for lbl, w in [("Parameter", self.param),
                       ("Value A",   self.value_a),
                       ("Value B",   self.value_b)]:
            f.addRow(lbl, w)

    def refresh(self, items): _fill_combo(self.param, items, prefer="volfrac")
    def key(self): return self.param.currentData() or self.param.currentText()


class SweepParamsGroup(QGroupBox):
    """Settings for a 1-D parameter sweep (visible only in Sweep mode)."""
    def __init__(self, parent=None):
        super().__init__("Sweep Parameters", parent)
        f = QFormLayout(self)
        self.param   = QComboBox()
        self.min_val = _dbl(0.08, -1e6, 1e6, dec=4, step=0.05)
        self.max_val = _dbl(0.60, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows  = _int(3, 1, 20); self.n_cols = _int(3, 1, 20)
        for lbl, w in [("Parameter", self.param), ("Min", self.min_val),
                       ("Max", self.max_val), ("Rows", self.n_rows), ("Cols", self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, items): _fill_combo(self.param, items, prefer="volfrac")
    def key(self):        return self.param.currentData() or self.param.currentText()


class Sweep2DParamsGroup(QGroupBox):
    """Settings for a 2-D parameter sweep (visible only in Sweep 2D mode)."""
    def __init__(self, parent=None):
        super().__init__("2D Sweep Parameters", parent)
        f = QFormLayout(self)
        self.row_param = QComboBox()
        self.row_min   = _dbl(0.10, -1e6, 1e6, dec=4, step=0.05)
        self.row_max   = _dbl(0.40, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows    = _int(2, 1, 20)
        self.col_param = QComboBox()
        self.col_min   = _dbl(0.40, -1e6, 1e6, dec=4, step=0.05)
        self.col_max   = _dbl(0.75, -1e6, 1e6, dec=4, step=0.05)
        self.n_cols    = _int(2, 1, 20)
        for lbl, w in [("Row param", self.row_param), ("Row min", self.row_min),
                       ("Row max", self.row_max),      ("N rows",  self.n_rows),
                       ("Col param", self.col_param),  ("Col min", self.col_min),
                       ("Col max",   self.col_max),    ("N cols",  self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, items):
        _fill_combo(self.row_param, items, prefer="volfrac")
        _fill_combo(self.col_param, items, prefer="m")
    def row_key(self):     return self.row_param.currentData() or self.row_param.currentText()
    def col_key(self):     return self.col_param.currentData() or self.col_param.currentText()


def _section(text):
    """Bold section-header label that spans both QFormLayout columns."""
    lbl = QLabel(f"<b>{text}</b>")
    return lbl


class SensitivitySweepParamsGroup(QGroupBox):
    """Combined settings for a 1-D sensitivity sweep.

    Shows both the sensitivity config (which param, base value, gap) and
    the sweep config (which param to vary, range, grid size).  The sweep
    parameter dropdown includes the sensitivity-specific options
    'Sensitivity base value' and 'Sensitivity gap' in addition to all
    regular config fields.
    """
    def __init__(self, parent=None):
        super().__init__("Sensitivity Sweep", parent)
        f = QFormLayout(self)

        f.addRow(_section("Sensitivity"))
        self.sens_param  = QComboBox()
        self.base_value  = _dbl(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap         = _dbl(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Sens. parameter", self.sens_param),
                       ("Base value",       self.base_value),
                       ("Gap (Δ)",          self.gap)]:
            f.addRow(lbl, w)

        f.addRow(_section("Sweep"))
        self.sweep_param = QComboBox()
        self.min_val = _dbl(0.15, -1e6, 1e6, dec=4, step=0.05)
        self.max_val = _dbl(0.45, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows  = _int(2, 1, 20)
        self.n_cols  = _int(3, 1, 20)
        for lbl, w in [("Sweep parameter", self.sweep_param),
                       ("Min",              self.min_val),
                       ("Max",              self.max_val),
                       ("Rows",             self.n_rows),
                       ("Cols",             self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, items):
        _fill_combo(self.sens_param, items, prefer="volfrac")
        _fill_sens_sweep_combo(self.sweep_param, items, prefer="sens.base_value")

    def sens_key(self):  return self.sens_param.currentData()  or self.sens_param.currentText()
    def sweep_key(self): return self.sweep_param.currentData() or self.sweep_param.currentText()


class SensitivitySweep2DParamsGroup(QGroupBox):
    """Combined settings for a 2-D sensitivity sweep.

    Sensitivity config section is shared; row and column sweep sections each
    have their own parameter dropdown (both include the sensitivity specials).
    """
    def __init__(self, parent=None):
        super().__init__("Sensitivity Sweep 2D", parent)
        f = QFormLayout(self)

        f.addRow(_section("Sensitivity"))
        self.sens_param = QComboBox()
        self.base_value = _dbl(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap        = _dbl(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Sens. parameter", self.sens_param),
                       ("Base value",       self.base_value),
                       ("Gap (Δ)",          self.gap)]:
            f.addRow(lbl, w)

        f.addRow(_section("Row sweep"))
        self.row_param = QComboBox()
        self.row_min = _dbl(0.15, -1e6, 1e6, dec=4, step=0.05)
        self.row_max = _dbl(0.45, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows  = _int(2, 1, 20)
        for lbl, w in [("Row parameter", self.row_param),
                       ("Row min",        self.row_min),
                       ("Row max",        self.row_max),
                       ("N rows",         self.n_rows)]:
            f.addRow(lbl, w)

        f.addRow(_section("Col sweep"))
        self.col_param = QComboBox()
        self.col_min = _dbl(0.02, -1e6, 1e6, dec=4, step=0.01)
        self.col_max = _dbl(0.10, -1e6, 1e6, dec=4, step=0.01)
        self.n_cols  = _int(2, 1, 20)
        for lbl, w in [("Col parameter", self.col_param),
                       ("Col min",        self.col_min),
                       ("Col max",        self.col_max),
                       ("N cols",         self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, items):
        _fill_combo(self.sens_param, items, prefer="volfrac")
        _fill_sens_sweep_combo(self.row_param, items, prefer="sens.base_value")
        _fill_sens_sweep_combo(self.col_param, items, prefer="sens.gap")

    def sens_key(self):      return self.sens_param.currentData()  or self.sens_param.currentText()
    def row_sweep_key(self): return self.row_param.currentData()   or self.row_param.currentText()
    def col_sweep_key(self): return self.col_param.currentData()   or self.col_param.currentText()


# ── Typed-row lists: filters, objective and constraints ──────────────────────
#
# A filter, an objective and a constraint are all a spec of the same shape,
# {"type": <plugin name>, <param>: <value>, ...}, so one row widget serves all
# three.  Rows are generated from plugin classes (name, label, params), so a new
# filter or response class appears here without editing this file.


class _SpecRow(QWidget):
    """One spec: a type selector, that type's generated parameters, and optionally ✕."""
    changed = Signal()   # the selected type changed

    def __init__(self, classes, on_remove=None, parent=None, spec=None):
        super().__init__(parent)
        self._classes = list(classes)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(2)

        header = QHBoxLayout()
        self._type = QComboBox()
        header.addWidget(self._type, 1)
        if on_remove is not None:
            remove = QPushButton("✕"); remove.setFixedWidth(28)
            remove.clicked.connect(lambda: on_remove(self))
            header.addWidget(remove)
        outer.addLayout(header)

        self._forms = {}
        for cls in self._classes:
            self._forms[cls.name] = ParamForm(cls.params, self)
            outer.addWidget(self._forms[cls.name])
        self._fill_types([cls.name for cls in self._classes])

        if spec:
            self.load_spec(spec)
        self._type.currentIndexChanged.connect(self._on_type_changed)
        self._on_type_changed()

        if on_remove is not None:
            line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Sunken)
            outer.addWidget(line)

    def _fill_types(self, names):
        current = self._type.currentData()
        self._type.blockSignals(True)
        self._type.clear()
        for cls in self._classes:
            if cls.name in names:
                self._type.addItem(cls.label, userData=cls.name)
        self._type.setCurrentIndex(max(self._type.findData(current), 0))
        self._type.blockSignals(False)

    def _on_type_changed(self, *_):
        key = self._type.currentData()
        for name, form in self._forms.items():
            form.setVisible(name == key)
        self.changed.emit()

    def offered_types(self):
        """The types currently offered by the selector, in menu order."""
        return [self._type.itemData(i) for i in range(self._type.count())]

    def set_allowed(self, names):
        """Offer only these types, keeping the current one when it is still allowed."""
        self._fill_types(list(names))
        self._on_type_changed()

    def get_spec(self):
        key = self._type.currentData()
        return {"type": key, **self._forms[key].get_values()}

    def load_spec(self, spec):
        values = dict(spec)
        key = values.pop("type", self._classes[0].name)
        index = self._type.findData(key)
        if index >= 0:
            self._type.setCurrentIndex(index)
        if key in self._forms:
            self._forms[key].set_values(values)


class SpecListGroup(QWidget):
    """A collapsible, ordered list of spec rows — the filter pipeline, the constraints.

    set_allowed() restricts the offered types to what the selected method can
    use.  With nothing allowed the group hides and get_specs() returns an empty
    list, so a run never receives entries its method would ignore or refuse.
    The rows are kept, so switching back to a method that can use them restores them.
    """
    changed = Signal()   # a row was added or removed, or changed type

    def __init__(self, title, classes, initial=(), noun="entry", parent=None):
        super().__init__(parent)
        self._title = title
        self._classes = list(classes)
        self._allowed = [cls.name for cls in self._classes]
        self._rows = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 4)
        outer.setSpacing(0)
        self._toggle = QPushButton()
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)
        self._toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._toggle.toggled.connect(self._on_toggle)
        outer.addWidget(self._toggle)

        self._body = QWidget()
        body = QVBoxLayout(self._body)
        body.setContentsMargins(4, 4, 4, 4)
        body.setSpacing(2)
        self._rows_container = QWidget()
        self._rows_box = QVBoxLayout(self._rows_container)
        self._rows_box.setContentsMargins(0, 0, 0, 0)
        self._rows_box.setSpacing(0)
        body.addWidget(self._rows_container)
        add = QPushButton(f"+ Add {noun}")
        add.clicked.connect(lambda: self._add_row())
        body.addWidget(add)
        outer.addWidget(self._body)

        for spec in initial:
            self._add_row(spec)
        self._refresh_label()

    def _on_toggle(self, checked):
        self._body.setVisible(checked)
        self._refresh_label()

    def _refresh_label(self):
        n = len(self._rows)
        suffix = f"({n} active)" if n else "(none active)"
        self._toggle.setText(f"{'▼' if self._toggle.isChecked() else '▶'}  {self._title}  {suffix}")

    def _add_row(self, spec=None):
        row = _SpecRow(self._classes, on_remove=self._remove_row, parent=self._rows_container, spec=spec)
        row.set_allowed(self._allowed)
        row.changed.connect(self.changed.emit)
        self._rows.append(row)
        self._rows_box.addWidget(row)
        self._refresh_label()
        self.changed.emit()

    def _remove_row(self, row):
        self._rows.remove(row)
        self._rows_box.removeWidget(row)
        row.hide()          # disappear now; Qt frees it on the next event-loop pass
        row.deleteLater()
        self._refresh_label()
        self.changed.emit()

    def set_allowed(self, names):
        """Offer only these types; with none allowed, hide and contribute nothing."""
        self._allowed = list(names)
        for row in self._rows:
            row.set_allowed(self._allowed)
        self.setVisible(bool(self._allowed))
        self.changed.emit()

    def get_specs(self):
        """The rows as spec dicts, in order; empty while no type is allowed."""
        if not self._allowed:
            return []
        return [row.get_spec() for row in self._rows]

    def load_specs(self, specs):
        """Replace every row with the given specs."""
        for row in list(self._rows):
            self._rows_box.removeWidget(row)
            row.hide()
            row.deleteLater()
        self._rows.clear()
        for spec in specs:
            self._add_row(spec)
        self._refresh_label()
        self.changed.emit()


class ObjectiveGroup(QWidget):
    """What the scenario minimises: one spec row generated from the response declarations."""
    changed = Signal()

    def __init__(self, classes, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        section = _CollapsibleSection("Objective", expanded=False)
        self._row = _SpecRow(classes)
        self._row.changed.connect(self.changed.emit)
        section.body_layout.addWidget(self._row)
        outer.addWidget(section)

    def offered_types(self):  return self._row.offered_types()
    def set_allowed(self, names): self._row.set_allowed(names)
    def get_spec(self):       return self._row.get_spec()
    def load_spec(self, spec):    self._row.load_spec(spec)
