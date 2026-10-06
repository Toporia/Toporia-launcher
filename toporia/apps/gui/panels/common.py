# apps/gui/panels/common.py — small pieces every panel uses.
#
#   CollapsibleSection     a titled section that folds open and shut
#   add_tooltip_row        a form row whose label and editor share a tooltip
#   double_box, int_box    spin boxes in one line
#   mark_availability      grey out plugins whose optional package is not installed
#   fill_combo             (re)fill a parameter-path dropdown, keeping the selection
#   section_label          a bold heading inside a form


from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# Extra items added to the sweep dropdown in sensitivity-sweep modes
SENS_SWEEP_EXTRA = [
    ("Sensitivity base value", "sens.base_value"),
    ("Sensitivity gap",        "sens.gap"),
]


# ── Spinbox factory helpers ───────────────────────────────────────────────────
# These avoid writing the same five lines every time a numeric input is needed.

def double_box(v, lo, hi, dec=3, step=0.1):
    """Create a floating-point spinbox with the given initial value, range, and step."""
    s = QDoubleSpinBox()
    s.setRange(lo, hi); s.setValue(v); s.setDecimals(dec); s.setSingleStep(step)
    return s

def int_box(v, lo, hi):
    """Create an integer spinbox."""
    s = QSpinBox(); s.setRange(lo, hi); s.setValue(v); return s


def add_tooltip_row(form, label, widget, tooltip):
    """Add a form row where both the label and editor explain the parameter."""
    lbl = QLabel(label)
    lbl.setToolTip(tooltip)
    widget.setToolTip(tooltip)
    form.addRow(lbl, widget)


class CollapsibleSection(QWidget):
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
        """Change the section's title, keeping its open or closed arrow."""
        self._title = title
        self._on_toggle(self._toggle.isChecked())


# ── Sweep dropdown helpers ────────────────────────────────────────────────────

def mark_availability(combo, classes):
    """Grey out every entry whose plugin needs a package that is not installed.

    The entry stays visible, says what it needs, and its tooltip gives the
    install command, so a missing optional dependency is explained up front
    instead of failing when a run starts.
    """
    from toporia.framework.registry import install_hint, missing_dependencies
    by_name = {cls.name: cls for cls in classes}
    for index in range(combo.count()):
        cls = by_name.get(combo.itemData(index))
        missing = missing_dependencies(cls) if cls is not None else []
        if not missing:
            continue
        item = combo.model().item(index)
        item.setEnabled(False)
        item.setText(f"{cls.label}  (needs {', '.join(missing)})")
        item.setToolTip(f"Not installed here. Install with:  {install_hint(missing)}")


def fill_combo(combo, items, prefer=""):
    """Rebuild a parameter dropdown from (label, parameter_path) pairs.

    The path is stored as the item's data and is what apply_param() receives;
    the items come from toporia.plugins.catalog.parameter_paths.  The previous
    selection is kept when it still exists, otherwise `prefer`, otherwise the first.
    """
    cur = combo.currentData() or prefer
    combo.blockSignals(True); combo.clear()
    for label, path in items:
        combo.addItem(label, userData=path)
    idx = combo.findData(cur); combo.setCurrentIndex(max(idx, 0))
    combo.blockSignals(False)


def fill_sens_sweep_combo(combo, items, prefer=""):
    """Like fill_combo but appends the two sensitivity-specific sweep targets."""
    fill_combo(combo, list(items) + SENS_SWEEP_EXTRA, prefer)




def section_label(text):
    """Bold section-header label that spans both QFormLayout columns."""
    lbl = QLabel(f"<b>{text}</b>")
    return lbl
