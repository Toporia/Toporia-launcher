# widgets.py — all parameter-editor UI components
#
# This file contains only Qt widgets.  There is no optimisation logic here
# and no matplotlib — it is purely about displaying and collecting user input.
#
# Widget hierarchy (what contains what):
#   MainWindow
#     └─ left panel
#          ├─ CoreParamsGroup    (method, mesh, material, solver settings)
#          ├─ LoadCasesGroup     (one LoadCaseRow per force)
#          ├─ SweepParamsGroup   (1-D sweep settings, hidden unless mode=Sweep)
#          └─ Sweep2DParamsGroup (2-D sweep settings, hidden unless mode=Sweep 2D)

from PySide6.QtWidgets import (
    QWidget, QGroupBox, QFormLayout, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox, QPushButton,
    QCheckBox, QFrame, QSizePolicy,
)
from PySide6.QtCore import Signal   # Qt signal/slot system (see python_primer.py §11)

# Parameters that are meaningful to sweep over (all are plain float/int fields
# on TopOptConfig).  Load-case sub-fields are added dynamically in _fill_combo.
SWEEP_PARAMS = [
    "volfrac", "m", "penal", "ls_dt", "ls_nrelax", "ls_delta", "ls_mu",
    "ls_gamma", "ls_init_hole_radius", "ls_rbf_c", "rmin", "max_iter", "tol",
]

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


LEVELSET_PARAM_HELP = {
    "ls_dt": (
        "Evolution step size for the level-set/RBF update. Larger values move the "
        "boundary faster; smaller values are more stable but slower."
    ),
    "ls_nrelax": (
        "Number of early iterations used to ramp from the initial volume toward "
        "the target before feedback volume control starts."
    ),
    "ls_delta": (
        "Half-width of the smooth Dirac-delta band around Phi=0. Larger values "
        "update a wider region around the boundary."
    ),
    "ls_mu": (
        "Volume penalty during the relaxation phase. Higher values push the "
        "design volume toward the target more strongly."
    ),
    "ls_gamma": (
        "Initial feedback gain for correcting volume after relaxation. Higher "
        "values react faster but can oscillate."
    ),
    "ls_gamma_step": (
        "Amount added to gamma each feedback iteration, until gamma reaches "
        "Gamma max."
    ),
    "ls_gamma_max": (
        "Upper limit on the feedback gain gamma. This prevents volume correction "
        "from becoming too aggressive."
    ),
    "ls_init_hole_radius": (
        "Initial circular hole radius as a fraction of the mesh height nely. "
        "This controls the starting topology pattern."
    ),
    "ls_rbf_c": (
        "Small regularization constant in the multiquadric RBF kernel. Usually "
        "kept near the TOPRBF default unless the RBF system is ill-conditioned."
    ),
    "ls_sample_step": (
        "Sampling spacing used to estimate each element's solid fraction. Smaller "
        "values are more accurate but slower."
    ),
    "ls_max_nodes": (
        "Maximum number of RBF nodes allowed before the method automatically uses "
        "a coarser internal mesh to avoid a huge dense matrix."
    ),
}


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

def _fill_combo(combo, n_cases, prefer=""):
    """Rebuild a parameter-selection dropdown to match the current number of load cases.

    Items are stored as (display_label, internal_key) pairs.
    Plain config fields use the field name as both label and key (e.g. "volfrac").
    Load-case sub-fields use display "LC 1 · Fmag" and key "lc0.Fmag".
    The key is what gets passed to apply_param() in config.py.
    """
    cur = combo.currentData() or prefer   # remember what was selected before rebuild
    combo.blockSignals(True); combo.clear()  # suppress change events while rebuilding

    items = [(p, p) for p in SWEEP_PARAMS]   # list of (label, key) tuples
    for i in range(n_cases):
        for field, lbl in [("Fmag", "Fmag"), ("Fa", "Angle"), ("weight", "Weight")]:
            items.append((f"LC {i+1} · {lbl}", f"lc{i}.{field}"))

    for lbl, key in items:
        combo.addItem(lbl, userData=key)   # userData stores the key invisibly alongside the label

    idx = combo.findData(cur); combo.setCurrentIndex(max(idx, 0))  # restore previous selection
    combo.blockSignals(False)  # re-enable change events


def _fill_sens_sweep_combo(combo, n_cases, prefer=""):
    """Like _fill_combo but appends the two sensitivity-specific sweep targets."""
    cur = combo.currentData() or prefer
    combo.blockSignals(True); combo.clear()

    items = [(p, p) for p in SWEEP_PARAMS]
    for i in range(n_cases):
        for field, lbl in [("Fmag", "Fmag"), ("Fa", "Angle"), ("weight", "Weight")]:
            items.append((f"LC {i+1} · {lbl}", f"lc{i}.{field}"))
    items += _SENS_SWEEP_EXTRA   # add "Sensitivity base value" and "Sensitivity gap"

    for lbl, key in items:
        combo.addItem(lbl, userData=key)

    idx = combo.findData(cur); combo.setCurrentIndex(max(idx, 0))
    combo.blockSignals(False)


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
        from toporia.core.config import LoadCase
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
        """Replace all rows with the load cases from a TopOptConfig."""
        for row in list(self._rows):
            self._vbox.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        for lc in cfg.load_cases:
            self._add(lc.Fmag, lc.Fa, lc.weight)


# ── Core and sweep parameter groups ──────────────────────────────────────────

class CoreParamsGroup(QWidget):
    """Fixed run controls split into focused sections."""
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        core = QGroupBox("Core Parameters")
        core_form = QFormLayout(core)
        self.m       = _dbl(1.0,  0.1,  5.0, dec=2)     # elements per mm
        self.volfrac = _dbl(0.25, 0.01, 1.0, step=0.05) # target material fraction
        _add_tooltip_row(core_form, "Mesh res m", self.m,
                         "Elements per millimeter. Higher values give finer designs but slower FEA.")
        _add_tooltip_row(core_form, "Vol fraction", self.volfrac,
                         "Target fraction of solid material allowed in the design.")
        outer.addWidget(core)

        opt = _CollapsibleSection("Optimizer", expanded=False)
        opt_form = QFormLayout()
        self.method = QComboBox()
        self.method.addItems(["density", "density_mma", "levelset"])
        _add_tooltip_row(opt_form, "Method", self.method,
                         "Optimization algorithm: OC density, MMA density, or RBF level-set.")

        self._density_panel = QWidget()
        density_form = QFormLayout(self._density_panel)
        density_form.setContentsMargins(0, 0, 0, 0)
        self.penal = _dbl(3.0, 1.0, 10.0, dec=1, step=0.5) # SIMP penalty
        _add_tooltip_row(density_form, "Penalty p", self.penal,
                         "SIMP penalty exponent. Higher values push density designs toward solid/void.")

        self._levelset_panel = QWidget()
        levelset_form = QFormLayout(self._levelset_panel)
        levelset_form.setContentsMargins(0, 0, 0, 0)
        levelset_warning = QLabel(
            "Warning: level set currently does not use the filter pipeline. "
            "Filter settings only affect density methods."
        )
        levelset_warning.setWordWrap(True)
        levelset_warning.setStyleSheet(
            "QLabel { color: #8a5a00; background: #fff4cc; border: 1px solid #e0b84d; "
            "padding: 4px; border-radius: 3px; }"
        )
        levelset_form.addRow(levelset_warning)
        self.ls_dt = _dbl(0.5, 0.001, 2.0, dec=3, step=0.05)
        self.ls_nrelax = _int(30, 1, 500)
        self.ls_delta = _dbl(10.0, 0.1, 100.0, dec=2, step=1.0)
        self.ls_mu = _dbl(20.0, 0.0, 500.0, dec=2, step=1.0)
        self.ls_gamma = _dbl(0.05, 0.0, 20.0, dec=3, step=0.05)
        self.ls_gamma_step = _dbl(0.05, 0.0, 20.0, dec=3, step=0.05)
        self.ls_gamma_max = _dbl(5.0, 0.0, 100.0, dec=2, step=0.5)
        self.ls_init_hole_radius = _dbl(0.1, 0.01, 0.5, dec=3, step=0.01)
        self.ls_rbf_c = _dbl(1e-4, 1e-8, 1e-1, dec=6, step=1e-4)
        self.ls_sample_step = _dbl(0.1, 0.05, 0.5, dec=2, step=0.05)
        self.ls_max_nodes = _int(3000, 100, 50000)
        _add_tooltip_row(levelset_form, "Step size", self.ls_dt, LEVELSET_PARAM_HELP["ls_dt"])
        _add_tooltip_row(levelset_form, "Relax iters", self.ls_nrelax, LEVELSET_PARAM_HELP["ls_nrelax"])
        _add_tooltip_row(levelset_form, "Delta band", self.ls_delta, LEVELSET_PARAM_HELP["ls_delta"])
        _add_tooltip_row(levelset_form, "Volume penalty", self.ls_mu, LEVELSET_PARAM_HELP["ls_mu"])
        _add_tooltip_row(levelset_form, "Gamma", self.ls_gamma, LEVELSET_PARAM_HELP["ls_gamma"])
        _add_tooltip_row(levelset_form, "Gamma step", self.ls_gamma_step, LEVELSET_PARAM_HELP["ls_gamma_step"])
        _add_tooltip_row(levelset_form, "Gamma max", self.ls_gamma_max, LEVELSET_PARAM_HELP["ls_gamma_max"])
        _add_tooltip_row(levelset_form, "Initial hole r", self.ls_init_hole_radius,
                         LEVELSET_PARAM_HELP["ls_init_hole_radius"])
        _add_tooltip_row(levelset_form, "RBF c", self.ls_rbf_c, LEVELSET_PARAM_HELP["ls_rbf_c"])
        _add_tooltip_row(levelset_form, "Sample step", self.ls_sample_step,
                         LEVELSET_PARAM_HELP["ls_sample_step"])
        _add_tooltip_row(levelset_form, "Max RBF nodes", self.ls_max_nodes,
                         LEVELSET_PARAM_HELP["ls_max_nodes"])

        opt.body_layout.addLayout(opt_form)
        opt.body_layout.addWidget(self._density_panel)
        opt.body_layout.addWidget(self._levelset_panel)
        outer.addWidget(opt)
        self.method.currentIndexChanged.connect(lambda _: self._update_method_panel())
        self._update_method_panel()

        conv = _CollapsibleSection("Convergence", expanded=False)
        conv_form = QFormLayout()
        self.max_iter = _int(100, 1, 2000)
        self.tol      = _dbl(0.01, 1e-6, 1.0, dec=4, step=0.005)
        _add_tooltip_row(conv_form, "Max iters", self.max_iter,
                         "Maximum number of optimization iterations before stopping.")
        _add_tooltip_row(conv_form, "Tolerance", self.tol,
                         "Convergence tolerance. Smaller values require more stable changes before stopping.")
        conv.body_layout.addLayout(conv_form)
        outer.addWidget(conv)

        output = _CollapsibleSection("Output", expanded=False)
        output_form = QFormLayout()
        self.save_every = _int(10, 0, 1000)
        _add_tooltip_row(output_form, "Save every N", self.save_every,
                         "Save an intermediate density image every N iterations. Use 0 for final only.")
        output.body_layout.addLayout(output_form)
        outer.addWidget(output)

    def _update_method_panel(self):
        """Show only the parameters relevant to the selected optimizer."""
        is_levelset = self.method.currentText() == "levelset"
        self._density_panel.setVisible(not is_levelset)
        self._levelset_panel.setVisible(is_levelset)

    def get_kwargs(self):
        """Return a dict of {field_name: value} ready to pass to TopOptConfig(**kw)."""
        return dict(method=self.method.currentText(), m=self.m.value(),
                    volfrac=self.volfrac.value(), penal=self.penal.value(),
                    ls_dt=self.ls_dt.value(), ls_nrelax=self.ls_nrelax.value(),
                    ls_delta=self.ls_delta.value(), ls_mu=self.ls_mu.value(),
                    ls_gamma=self.ls_gamma.value(), ls_gamma_step=self.ls_gamma_step.value(),
                    ls_gamma_max=self.ls_gamma_max.value(),
                    ls_init_hole_radius=self.ls_init_hole_radius.value(),
                    ls_rbf_c=self.ls_rbf_c.value(),
                    ls_sample_step=self.ls_sample_step.value(),
                    ls_max_nodes=self.ls_max_nodes.value(),
                    max_iter=self.max_iter.value(), tol=self.tol.value(),
                    save_every=self.save_every.value())

    def load_from_config(self, cfg):
        """Populate all spinboxes from a TopOptConfig (called when a configuration is selected)."""
        idx = self.method.findText(cfg.method)
        if idx >= 0:
            self.method.setCurrentIndex(idx)
        self._update_method_panel()
        self.m.setValue(cfg.m)
        self.volfrac.setValue(cfg.volfrac)
        self.penal.setValue(cfg.penal)
        self.ls_dt.setValue(cfg.ls_dt)
        self.ls_nrelax.setValue(cfg.ls_nrelax)
        self.ls_delta.setValue(cfg.ls_delta)
        self.ls_mu.setValue(cfg.ls_mu)
        self.ls_gamma.setValue(cfg.ls_gamma)
        self.ls_gamma_step.setValue(cfg.ls_gamma_step)
        self.ls_gamma_max.setValue(cfg.ls_gamma_max)
        self.ls_init_hole_radius.setValue(cfg.ls_init_hole_radius)
        self.ls_rbf_c.setValue(cfg.ls_rbf_c)
        self.ls_sample_step.setValue(cfg.ls_sample_step)
        self.ls_max_nodes.setValue(cfg.ls_max_nodes)
        self.max_iter.setValue(cfg.max_iter)
        self.tol.setValue(cfg.tol)
        self.save_every.setValue(cfg.save_every)


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
        self.param      = QComboBox(); _fill_combo(self.param, 2)
        self.base_value = _dbl(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap        = _dbl(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Parameter",  self.param),
                       ("Base value", self.base_value),
                       ("Gap (Δ)",    self.gap)]:
            f.addRow(lbl, w)

    def refresh(self, n): _fill_combo(self.param, n)
    def key(self): return self.param.currentData() or self.param.currentText()


class CompareTwoParamsGroup(QGroupBox):
    """Settings for a two-run comparison (visible only in Compare Two mode).

    The user picks one parameter to vary, sets two values (A and B), and
    optionally adjusts the density threshold used to classify solid vs void.
    """
    def __init__(self, parent=None):
        super().__init__("Compare Two Parameters", parent)
        f = QFormLayout(self)
        self.param   = QComboBox(); _fill_combo(self.param, 2)
        self.value_a = _dbl(0.20, -1e6, 1e6, dec=4, step=0.05)
        self.value_b = _dbl(0.40, -1e6, 1e6, dec=4, step=0.05)
        for lbl, w in [("Parameter", self.param),
                       ("Value A",   self.value_a),
                       ("Value B",   self.value_b)]:
            f.addRow(lbl, w)

    def refresh(self, n): _fill_combo(self.param, n)
    def key(self): return self.param.currentData() or self.param.currentText()


class SweepParamsGroup(QGroupBox):
    """Settings for a 1-D parameter sweep (visible only in Sweep mode)."""
    def __init__(self, parent=None):
        super().__init__("Sweep Parameters", parent)
        f = QFormLayout(self)
        self.param   = QComboBox(); _fill_combo(self.param, 2)  # 2 = default load case count
        self.min_val = _dbl(0.08, -1e6, 1e6, dec=4, step=0.05)
        self.max_val = _dbl(0.60, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows  = _int(3, 1, 20); self.n_cols = _int(3, 1, 20)
        for lbl, w in [("Parameter", self.param), ("Min", self.min_val),
                       ("Max", self.max_val), ("Rows", self.n_rows), ("Cols", self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, n): _fill_combo(self.param, n)  # called when load cases change
    def key(self):        return self.param.currentData() or self.param.currentText()


class Sweep2DParamsGroup(QGroupBox):
    """Settings for a 2-D parameter sweep (visible only in Sweep 2D mode)."""
    def __init__(self, parent=None):
        super().__init__("2D Sweep Parameters", parent)
        f = QFormLayout(self)
        self.row_param = QComboBox(); _fill_combo(self.row_param, 2)
        self.row_min   = _dbl(0.10, -1e6, 1e6, dec=4, step=0.05)
        self.row_max   = _dbl(0.40, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows    = _int(2, 1, 20)
        self.col_param = QComboBox(); _fill_combo(self.col_param, 2, prefer="m")
        self.col_min   = _dbl(0.40, -1e6, 1e6, dec=4, step=0.05)
        self.col_max   = _dbl(0.75, -1e6, 1e6, dec=4, step=0.05)
        self.n_cols    = _int(2, 1, 20)
        for lbl, w in [("Row param", self.row_param), ("Row min", self.row_min),
                       ("Row max", self.row_max),      ("N rows",  self.n_rows),
                       ("Col param", self.col_param),  ("Col min", self.col_min),
                       ("Col max",   self.col_max),    ("N cols",  self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, n):  _fill_combo(self.row_param, n); _fill_combo(self.col_param, n)
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
        self.sens_param  = QComboBox(); _fill_combo(self.sens_param, 2)
        self.base_value  = _dbl(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap         = _dbl(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Sens. parameter", self.sens_param),
                       ("Base value",       self.base_value),
                       ("Gap (Δ)",          self.gap)]:
            f.addRow(lbl, w)

        f.addRow(_section("Sweep"))
        self.sweep_param = QComboBox()
        _fill_sens_sweep_combo(self.sweep_param, 2, prefer="sens.base_value")
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

    def refresh(self, n):
        _fill_combo(self.sens_param, n)
        _fill_sens_sweep_combo(self.sweep_param, n)

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
        self.sens_param = QComboBox(); _fill_combo(self.sens_param, 2)
        self.base_value = _dbl(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap        = _dbl(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Sens. parameter", self.sens_param),
                       ("Base value",       self.base_value),
                       ("Gap (Δ)",          self.gap)]:
            f.addRow(lbl, w)

        f.addRow(_section("Row sweep"))
        self.row_param = QComboBox()
        _fill_sens_sweep_combo(self.row_param, 2, prefer="sens.base_value")
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
        _fill_sens_sweep_combo(self.col_param, 2, prefer="sens.gap")
        self.col_min = _dbl(0.02, -1e6, 1e6, dec=4, step=0.01)
        self.col_max = _dbl(0.10, -1e6, 1e6, dec=4, step=0.01)
        self.n_cols  = _int(2, 1, 20)
        for lbl, w in [("Col parameter", self.col_param),
                       ("Col min",        self.col_min),
                       ("Col max",        self.col_max),
                       ("N cols",         self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, n):
        _fill_combo(self.sens_param, n)
        _fill_sens_sweep_combo(self.row_param, n)
        _fill_sens_sweep_combo(self.col_param, n)

    def sens_key(self):      return self.sens_param.currentData()  or self.sens_param.currentText()
    def row_sweep_key(self): return self.row_param.currentData()   or self.row_param.currentText()
    def col_sweep_key(self): return self.col_param.currentData()   or self.col_param.currentText()


# ── Filter pipeline widgets ───────────────────────────────────────────────────

# AM filter directions: (integer value passed to AMFilter, display label).
# 0 = build up from image bottom, 90 = build right from image left, etc.
_AM_DIRECTIONS = [
    (  0, "0° — base bottom, build up ↑"),
    ( 90, "90° — base left,  build right →"),
    (180, "180° — base top,  build down ↓"),
    (270, "270° — base right, build left ←"),
]


class _FilterParams(QWidget):
    """Parameter sub-panel for one filter type, shown inside a FilterRow."""

    def __init__(self, ftype, parent=None):
        super().__init__(parent)
        f = QFormLayout(self)
        f.setContentsMargins(0, 0, 0, 0)
        self.ftype = ftype

        if ftype == "density":
            self.rmin = _dbl(0.0, 0.0, 20.0, dec=2, step=0.5)
            self.rmin.setSpecialValueText("(use rmin)")   # 0.0 means "use config.rmin"
            f.addRow("rmin", self.rmin)

        elif ftype == "sensitivity":
            self.rmin = _dbl(0.0, 0.0, 20.0, dec=2, step=0.5)
            self.rmin.setSpecialValueText("(use rmin)")   # 0.0 means "use config.rmin"
            f.addRow("rmin", self.rmin)

        elif ftype == "heaviside":
            self.beta          = _dbl(1.0,  0.1, 128.0, dec=1, step=1.0)
            self.eta           = _dbl(0.5,  0.0,   1.0, dec=2, step=0.05)
            self.beta_max      = _dbl(32.0, 1.0, 512.0, dec=0, step=8.0)
            self.beta_interval = _int(25, 1, 500)
            f.addRow("beta",          self.beta)
            f.addRow("eta",           self.eta)
            f.addRow("beta max",      self.beta_max)
            f.addRow("beta interval", self.beta_interval)

        elif ftype == "am":
            self.direction = QComboBox()
            for val, label in _AM_DIRECTIONS:
                self.direction.addItem(label, userData=val)
            f.addRow("Direction", self.direction)
            self.overhang = _dbl(45.0, 0.0, 89.9, dec=1, step=5.0)
            self.overhang.setToolTip("0=pillars only · 45=standard 45° rule · 89.9≈no constraint")
            f.addRow("Overhang °", self.overhang)

        elif ftype == "routing":
            self.radius_mm = _dbl(2.0, 0.0, 100.0, dec=2, step=0.5)
            self.radius_mm.setToolTip("2D router tool radius in mm")
            self.P = _dbl(20.0, 1.0, 200.0, dec=0, step=5.0)
            self.start_iter = _int(20, 0, 2000)
            self.start_iter.setToolTip("Iteration where the routing filter starts to take effect")
            self.ramp_iters = _int(20, 1, 2000)
            self.ramp_iters.setToolTip("Iterations used to blend from identity to full routing")
            self.threshold = _dbl(0.05, 0.0, 1.0, dec=3, step=0.01)
            self.threshold.setToolTip(
                "Density below which elements are treated as void for dilation.\n"
                "Prevents low-density scatter from seeding unwanted solid growth."
            )
            f.addRow("Radius mm", self.radius_mm)
            f.addRow("P (sharpness)", self.P)
            f.addRow("Start iter", self.start_iter)
            f.addRow("Ramp iters", self.ramp_iters)
            f.addRow("Threshold", self.threshold)

        elif ftype == "symmetry":
            self.axis = QComboBox()
            self.axis.addItem("Left-right", userData="left_right")
            self.axis.addItem("Bottom-top", userData="bottom_top")
            self.axis.addItem("Both", userData="both")
            self.axis.setToolTip("Mirror-average the density field around the selected centerline")
            f.addRow("Axis", self.axis)

    def get_spec(self):
        """Return a filter spec dict for this filter type."""
        spec = {"type": self.ftype}
        if self.ftype == "density":
            v = self.rmin.value()
            if v > 0.0:
                spec["rmin"] = v
        elif self.ftype == "sensitivity":
            v = self.rmin.value()
            if v > 0.0:
                spec["rmin"] = v
        elif self.ftype == "heaviside":
            spec["beta"]          = self.beta.value()
            spec["eta"]           = self.eta.value()
            spec["beta_max"]      = self.beta_max.value()
            spec["beta_interval"] = self.beta_interval.value()
        elif self.ftype == "am":
            spec["direction"]      = self.direction.currentData()
            spec["overhang_angle"] = self.overhang.value()
        elif self.ftype == "routing":
            spec["radius_mm"]  = self.radius_mm.value()
            spec["P"]          = self.P.value()
            spec["start_iter"] = self.start_iter.value()
            spec["ramp_iters"] = self.ramp_iters.value()
            spec["threshold"]  = self.threshold.value()
        elif self.ftype == "symmetry":
            spec["axis"] = self.axis.currentData()
        return spec

    def load_spec(self, spec):
        """Populate this panel from a filter spec dict."""
        if self.ftype in {"density", "sensitivity"}:
            self.rmin.setValue(float(spec.get("rmin", 0.0) or 0.0))
        elif self.ftype == "heaviside":
            self.beta.setValue(float(spec.get("beta", 1.0)))
            self.eta.setValue(float(spec.get("eta", 0.5)))
            self.beta_max.setValue(float(spec.get("beta_max", 32.0)))
            self.beta_interval.setValue(int(spec.get("beta_interval", 25)))
        elif self.ftype == "am":
            idx = self.direction.findData(spec.get("direction", 0))
            if idx >= 0:
                self.direction.setCurrentIndex(idx)
            self.overhang.setValue(float(spec.get("overhang_angle", 45.0)))
        elif self.ftype == "routing":
            self.radius_mm.setValue(float(spec.get("radius_mm", 2.0)))
            self.P.setValue(float(spec.get("P", 20.0)))
            self.start_iter.setValue(int(spec.get("start_iter", 20)))
            self.ramp_iters.setValue(int(spec.get("ramp_iters", 20)))
            self.threshold.setValue(float(spec.get("threshold", 0.05)))
        elif self.ftype == "symmetry":
            idx = self.axis.findData(spec.get("axis", "left_right"))
            if idx >= 0:
                self.axis.setCurrentIndex(idx)


class _FilterRow(QWidget):
    """One row in the filter pipeline: type selector + parameters + remove button."""

    def __init__(self, on_remove, parent=None, spec=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(2)

        # Header: type dropdown + remove button
        hdr = QHBoxLayout()
        self._type = QComboBox()
        for label, key in [("Density filter",     "density"),
                           ("Sensitivity filter", "sensitivity"),
                           ("Heaviside (project)", "heaviside"),
                           ("AM overhang filter",  "am"),
                           ("Routing radius filter", "routing"),
                           ("Symmetry filter", "symmetry")]:
            self._type.addItem(label, userData=key)
        hdr.addWidget(self._type, 1)
        btn = QPushButton("✕"); btn.setFixedWidth(28)
        btn.clicked.connect(lambda: on_remove(self) if on_remove else None)
        hdr.addWidget(btn)
        outer.addLayout(hdr)

        # Parameter panels — one per type, swapped on type change
        self._panels = {}
        for key in ("density", "sensitivity", "heaviside", "am", "routing", "symmetry"):
            p = _FilterParams(key, self)
            self._panels[key] = p
            outer.addWidget(p)

        self._type.currentIndexChanged.connect(self._on_type_changed)
        if spec:
            key = spec.get("type", "density")
            idx = self._type.findData(key)
            if idx >= 0:
                self._type.setCurrentIndex(idx)
                self._panels[key].load_spec(spec)
        self._on_type_changed(0)   # show selected panel

        # Separator line
        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        outer.addWidget(line)

    def _on_type_changed(self, _):
        key = self._type.currentData()
        for k, p in self._panels.items():
            p.setVisible(k == key)

    def get_spec(self):
        key = self._type.currentData()
        return self._panels[key].get_spec()


class FilterPipelineGroup(QWidget):
    """Collapsible filter pipeline editor.

    Shows a toggle button that expands/collapses the filter list.
    Positioned above Load Cases in the left panel.
    Produces a list of filter spec dicts via get_filter_specs().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 4)
        outer.setSpacing(0)

        # Collapsible toggle button
        self._toggle = QPushButton("▼  Filters  (1 active)")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)   # expanded on startup
        self._toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._toggle.toggled.connect(self._on_toggle)
        outer.addWidget(self._toggle)

        # Body
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(4, 4, 4, 4)
        body_layout.setSpacing(2)

        rmin_form = QFormLayout()
        self.rmin = _dbl(1.5, 0.5, 10.0, dec=2, step=0.5)
        rmin_form.addRow("Default rmin", self.rmin)
        body_layout.addLayout(rmin_form)

        self._rows = []
        self._rows_container = QWidget()
        self._rows_vbox = QVBoxLayout(self._rows_container)
        self._rows_vbox.setContentsMargins(0, 0, 0, 0)
        self._rows_vbox.setSpacing(0)
        body_layout.addWidget(self._rows_container)

        add_btn = QPushButton("+ Add filter")
        add_btn.clicked.connect(lambda: self._add_row())
        body_layout.addWidget(add_btn)

        self._body.setVisible(True)
        outer.addWidget(self._body)

        # Pre-populate with the default DensityFilter.
        # Remove it to run with no filtering at all (raw optimiser output).
        self._add_row()

    # ── internal helpers ──────────────────────────────────────────────────────

    def _on_toggle(self, checked):
        self._body.setVisible(checked)
        n = len(self._rows)
        suffix = f"({n} active)" if n else "(none active)"
        self._toggle.setText(f"{'▼' if checked else '▶'}  Filters  {suffix}")

    def _add_row(self, spec=None):
        row = _FilterRow(on_remove=self._remove_row, parent=self._rows_container, spec=spec)
        self._rows.append(row)
        self._rows_vbox.addWidget(row)
        self._refresh_label()

    def _remove_row(self, row):
        self._rows.remove(row)
        self._rows_vbox.removeWidget(row)
        row.deleteLater()
        self._refresh_label()

    def _refresh_label(self):
        n = len(self._rows)
        suffix = f"({n} active)" if n else "(none active)"
        expanded = self._toggle.isChecked()
        self._toggle.setText(f"{'▼' if expanded else '▶'}  Filters  {suffix}")

    # ── public API ────────────────────────────────────────────────────────────

    def get_filter_specs(self):
        """Return list of filter spec dicts in pipeline order."""
        return [r.get_spec() for r in self._rows]

    def get_default_rmin(self):
        return self.rmin.value()

    def load_from_config(self, cfg):
        """Replace filter rows with the explicit pipeline from a TopOptConfig."""
        self.rmin.setValue(cfg.rmin)
        for row in list(self._rows):
            self._rows_vbox.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        for spec in getattr(cfg, "filter_specs", []) or []:
            self._add_row(spec)
        self._refresh_label()
