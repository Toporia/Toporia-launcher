# apps/gui/panels/modes.py — the settings of each analysis mode.
#
# One group per entry in the Mode menu (sweep, compare, sensitivity, ...);
# the window shows only the selected mode's group.  Every parameter dropdown
# lists the setup's parameter paths (plugins/catalog.py), so anything numeric
# can be swept, compared or perturbed.
#
# Every group offers the same small interface to the window:
#   refresh(items)   refill its parameter dropdowns from (label, path) pairs
#   key(), row_key(), sens_key(), ...   the parameter path currently selected


from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from .common import (
    double_box,
    fill_combo,
    fill_sens_sweep_combo,
    int_box,
    section_label,
)
from .loads import LoadCasesGroup


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
        self.base_value = double_box(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap        = double_box(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Parameter",  self.param),
                       ("Base value", self.base_value),
                       ("Gap (Δ)",    self.gap)]:
            f.addRow(lbl, w)

    def refresh(self, items): fill_combo(self.param, items, prefer="volfrac")
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
        self.value_a = double_box(0.20, -1e6, 1e6, dec=4, step=0.05)
        self.value_b = double_box(0.40, -1e6, 1e6, dec=4, step=0.05)
        for lbl, w in [("Parameter", self.param),
                       ("Value A",   self.value_a),
                       ("Value B",   self.value_b)]:
            f.addRow(lbl, w)

    def refresh(self, items): fill_combo(self.param, items, prefer="volfrac")
    def key(self): return self.param.currentData() or self.param.currentText()


class SweepParamsGroup(QGroupBox):
    """Settings for a 1-D parameter sweep (visible only in Sweep mode)."""
    def __init__(self, parent=None):
        super().__init__("Sweep Parameters", parent)
        f = QFormLayout(self)
        self.param   = QComboBox()
        self.min_val = double_box(0.08, -1e6, 1e6, dec=4, step=0.05)
        self.max_val = double_box(0.60, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows  = int_box(3, 1, 20); self.n_cols = int_box(3, 1, 20)
        for lbl, w in [("Parameter", self.param), ("Min", self.min_val),
                       ("Max", self.max_val), ("Rows", self.n_rows), ("Cols", self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, items): fill_combo(self.param, items, prefer="volfrac")
    def key(self):        return self.param.currentData() or self.param.currentText()


class Sweep2DParamsGroup(QGroupBox):
    """Settings for a 2-D parameter sweep (visible only in Sweep 2D mode)."""
    def __init__(self, parent=None):
        super().__init__("2D Sweep Parameters", parent)
        f = QFormLayout(self)
        self.row_param = QComboBox()
        self.row_min   = double_box(0.10, -1e6, 1e6, dec=4, step=0.05)
        self.row_max   = double_box(0.40, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows    = int_box(2, 1, 20)
        self.col_param = QComboBox()
        self.col_min   = double_box(0.40, -1e6, 1e6, dec=4, step=0.05)
        self.col_max   = double_box(0.75, -1e6, 1e6, dec=4, step=0.05)
        self.n_cols    = int_box(2, 1, 20)
        for lbl, w in [("Row param", self.row_param), ("Row min", self.row_min),
                       ("Row max", self.row_max),      ("N rows",  self.n_rows),
                       ("Col param", self.col_param),  ("Col min", self.col_min),
                       ("Col max",   self.col_max),    ("N cols",  self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, items):
        fill_combo(self.row_param, items, prefer="volfrac")
        fill_combo(self.col_param, items, prefer="m")
    def row_key(self):     return self.row_param.currentData() or self.row_param.currentText()
    def col_key(self):     return self.col_param.currentData() or self.col_param.currentText()



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

        f.addRow(section_label("Sensitivity"))
        self.sens_param  = QComboBox()
        self.base_value  = double_box(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap         = double_box(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Sens. parameter", self.sens_param),
                       ("Base value",       self.base_value),
                       ("Gap (Δ)",          self.gap)]:
            f.addRow(lbl, w)

        f.addRow(section_label("Sweep"))
        self.sweep_param = QComboBox()
        self.min_val = double_box(0.15, -1e6, 1e6, dec=4, step=0.05)
        self.max_val = double_box(0.45, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows  = int_box(2, 1, 20)
        self.n_cols  = int_box(3, 1, 20)
        for lbl, w in [("Sweep parameter", self.sweep_param),
                       ("Min",              self.min_val),
                       ("Max",              self.max_val),
                       ("Rows",             self.n_rows),
                       ("Cols",             self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, items):
        fill_combo(self.sens_param, items, prefer="volfrac")
        fill_sens_sweep_combo(self.sweep_param, items, prefer="sens.base_value")

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

        f.addRow(section_label("Sensitivity"))
        self.sens_param = QComboBox()
        self.base_value = double_box(0.30, -1e6, 1e6, dec=4, step=0.05)
        self.gap        = double_box(0.05,  1e-6, 1e6, dec=4, step=0.01)
        for lbl, w in [("Sens. parameter", self.sens_param),
                       ("Base value",       self.base_value),
                       ("Gap (Δ)",          self.gap)]:
            f.addRow(lbl, w)

        f.addRow(section_label("Row sweep"))
        self.row_param = QComboBox()
        self.row_min = double_box(0.15, -1e6, 1e6, dec=4, step=0.05)
        self.row_max = double_box(0.45, -1e6, 1e6, dec=4, step=0.05)
        self.n_rows  = int_box(2, 1, 20)
        for lbl, w in [("Row parameter", self.row_param),
                       ("Row min",        self.row_min),
                       ("Row max",        self.row_max),
                       ("N rows",         self.n_rows)]:
            f.addRow(lbl, w)

        f.addRow(section_label("Col sweep"))
        self.col_param = QComboBox()
        self.col_min = double_box(0.02, -1e6, 1e6, dec=4, step=0.01)
        self.col_max = double_box(0.10, -1e6, 1e6, dec=4, step=0.01)
        self.n_cols  = int_box(2, 1, 20)
        for lbl, w in [("Col parameter", self.col_param),
                       ("Col min",        self.col_min),
                       ("Col max",        self.col_max),
                       ("N cols",         self.n_cols)]:
            f.addRow(lbl, w)

    def refresh(self, items):
        fill_combo(self.sens_param, items, prefer="volfrac")
        fill_sens_sweep_combo(self.row_param, items, prefer="sens.base_value")
        fill_sens_sweep_combo(self.col_param, items, prefer="sens.gap")

    def sens_key(self):      return self.sens_param.currentData()  or self.sens_param.currentText()
    def row_sweep_key(self): return self.row_param.currentData()   or self.row_param.currentText()
    def col_sweep_key(self): return self.col_param.currentData()   or self.col_param.currentText()


class CompareMethodsParamsGroup(QGroupBox):
    """Which methods to compare on the current problem (visible only in Compare Methods mode).

    Every selectable method is listed — every physics model with every updater,
    and the whole methods — with the four classic ones ticked.  Each ticked
    method runs on the same scenario, mesh, filters and stopping rule; the
    results are one image of the designs and one table, also in the log.
    """
    #: Ticked when the panel is first shown.
    DEFAULT = ("q4+oc", "q4+mma", "q4+simpl", "q4+beso")

    def __init__(self, parent=None):
        super().__init__("Compare Methods", parent)
        from toporia.framework.registry import missing_dependencies
        from toporia.plugins.methods import method_classes
        layout = QVBoxLayout(self)
        hint = QLabel("Ticked methods run on this problem with the same mesh, filters and "
                      "stopping rule. A method that cannot solve it is listed with the reason.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.methods = QListWidget()
        for cls in method_classes():
            # The updater first: in a long list of pairings it is what tells them apart.
            model, updater = getattr(cls, "model", None), getattr(cls, "updater", None)
            text = f"{updater.label}  ·  on {model.name}" if model else f"{cls.label}  (whole method)"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cls.name)
            item.setToolTip(f"{cls.label}   [{cls.name}]")
            missing = missing_dependencies(cls)
            if missing:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setToolTip(f"{cls.label}: needs {', '.join(missing)}, which is not installed")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if cls.name in self.DEFAULT and not missing else Qt.Unchecked)
            self.methods.addItem(item)
        self.methods.setMinimumHeight(180)
        layout.addWidget(self.methods)

    def selected(self):
        """The ticked methods' names, in list order."""
        return [self.methods.item(i).data(Qt.UserRole) for i in range(self.methods.count())
                if self.methods.item(i).checkState() == Qt.Checked]

    def set_selected(self, names):
        """Tick exactly these methods."""
        for i in range(self.methods.count()):
            item = self.methods.item(i)
            item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in names else Qt.Unchecked)

    def refresh(self, items):
        """The method list does not depend on the parameter paths."""
