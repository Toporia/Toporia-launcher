# apps/gui/panels/loads.py — the load cases: one row per force (magnitude, angle, weight).


from PySide6.QtCore import Signal  # Qt signal/slot system (see python_primer.py §11)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .common import (
    CollapsibleSection,
    double_box,
)


class LoadCaseRow(QWidget):
    """One horizontal row representing a single load case.

    Contains: numbered label | Fmag spinbox | Angle spinbox | Weight spinbox | ✕ button
    """
    def __init__(self, n, fmag=1.0, fa=0.0, weight=1.0, on_remove=None, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self); row.setContentsMargins(0, 2, 0, 2)

        self._lbl = QLabel(f"<b>LC {n}</b>"); self._lbl.setFixedWidth(36)  # bold HTML label
        row.addWidget(self._lbl)

        self.fmag   = double_box(fmag,   0, 1e6, dec=1)              # force magnitude spinbox
        self.fa     = double_box(fa,  -360, 360, dec=1, step=15.0)   # angle in degrees
        self.weight = double_box(weight, 0,   1, dec=1, step=0.1)    # compliance weight (should sum to 1)

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
        from toporia.framework import LoadCase
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
        self.section_label = CollapsibleSection("Load Cases", expanded=False)
        outer.addWidget(self.section_label)

        self._vbox = self.section_label.body_layout
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
        self.section_label.set_title(title)

    def load_from_config(self, cfg):
        """Replace all rows with the load cases from a Run."""
        for row in list(self._rows):
            self._vbox.removeWidget(row)
            row.hide()          # disappear now; Qt frees it on the next event-loop pass
            row.deleteLater()
        self._rows.clear()
        for lc in cfg.scenario.load_cases:
            self._add(lc.Fmag, lc.Fa, lc.weight)
