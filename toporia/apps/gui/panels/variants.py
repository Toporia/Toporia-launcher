# apps/gui/panels/variants.py — evaluate every design in several versions (solver.variants).
#
# One parameter path, a list of values, and how the versions are joined: the
# worst case (robust design) or the mean (an expected value).  The button fills
# in the classic robust formulation — eroded, intermediate and dilated
# projections, Wang, Lazarov & Sigmund 2011 — on the first Heaviside filter.
# See framework/parts/variants.py.

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .common import CollapsibleSection, add_tooltip_row, double_box, fill_combo, int_box


class VariantsGroup(QWidget):
    """Variants of each design (robust design, uncertain loads): off by default."""
    changed = Signal()
    robust_requested = Signal()   # the window adds or finds a Heaviside filter and calls use_robust_projection

    def __init__(self, parent=None):
        super().__init__(parent)
        from toporia.framework.parts.variants import COMBINE
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._section = CollapsibleSection("Variants (robust design)", expanded=False)
        outer.addWidget(self._section)

        self.enabled = QCheckBox("Evaluate every design in several versions")
        self._section.body_layout.addWidget(self.enabled)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        self.path = QComboBox()
        self.values = QLineEdit("0.75, 0.5, 0.25")
        self.combine = QComboBox()
        for key, label in COMBINE.items():
            self.combine.addItem(label, userData=key)
        self.nominal = int_box(1, 0, 20)
        self.sharpness = double_box(50.0, 1.0, 1000.0, dec=1, step=10.0)
        add_tooltip_row(form, "Parameter", self.path, "The parameter that differs between the versions.")
        add_tooltip_row(form, "Values", self.values, "One version per value, separated by commas.")
        add_tooltip_row(form, "Combine", self.combine,
                        "Worst case: a smooth maximum, for robust design. Mean: an expected value.")
        add_tooltip_row(form, "Shown version", self.nominal,
                        "Which version (counting from 0) is drawn and held to the volume budget.")
        add_tooltip_row(form, "Sharpness", self.sharpness,
                        "Of the smooth maximum: within log(n)/sharpness of the true worst case.")
        self._section.body_layout.addWidget(form_widget)
        robust = QPushButton("Robust projection: eroded / intermediate / dilated")
        robust.setToolTip("Wang, Lazarov & Sigmund (2011): the worst of three Heaviside thresholds, "
                          "for a minimum length scale and tolerance to manufacturing error.")
        robust.clicked.connect(self.robust_requested.emit)
        self._section.body_layout.addWidget(robust)

        self.enabled.toggled.connect(self._on_enabled)
        for signal in (self.path.currentIndexChanged, self.values.editingFinished,
                       self.combine.currentIndexChanged, self.nominal.valueChanged, self.sharpness.valueChanged):
            signal.connect(lambda *_: self.changed.emit())
        self._form = form_widget
        self._on_enabled(False)

    def _on_enabled(self, on):
        self._form.setEnabled(on)
        self._section.set_title("Variants (robust design)" + ("  (on)" if on else ""))
        self.changed.emit()

    def set_paths(self, items):
        """The parameter paths a version may vary (the mesh resolution excluded).

        The chosen path is kept even while the setup does not offer it (a whole
        method has no filters), so switching back restores it.
        """
        wanted = self.path.currentData()
        items = [(label, path) for label, path in items if path != "m"]
        if wanted and wanted not in [path for _, path in items]:
            items.append((wanted, wanted))
        fill_combo(self.path, items)

    def use_robust_projection(self, filter_index):
        """Fill in the robust formulation on the Heaviside filter at `filter_index`."""
        path = f"filters[{filter_index}].eta"
        if self.path.findData(path) < 0:
            self.path.addItem(path, userData=path)
        self.path.setCurrentIndex(self.path.findData(path))
        self.values.setText("0.75, 0.5, 0.25")
        self.combine.setCurrentIndex(self.combine.findData("worst"))
        self.nominal.setValue(1)
        self.enabled.setChecked(True)
        self.changed.emit()

    def get_spec(self):
        """solver.variants: {} when off."""
        if not self.enabled.isChecked() or self.isHidden():
            return {}
        try:
            values = [float(text) for text in self.values.text().replace(";", ",").split(",") if text.strip()]
        except ValueError:
            values = []
        return {"path": self.path.currentData(), "values": values, "combine": self.combine.currentData(),
                "nominal": self.nominal.value(), "sharpness": self.sharpness.value()}

    def load_spec(self, spec):
        spec = dict(spec or {})
        self.enabled.blockSignals(True)
        self.enabled.setChecked(bool(spec))
        self.enabled.blockSignals(False)
        if spec:
            path = spec.get("path")
            if self.path.findData(path) < 0:
                self.path.addItem(path, userData=path)
            self.path.setCurrentIndex(self.path.findData(path))
            self.values.setText(", ".join(f"{v:g}" for v in spec.get("values", ())))
            self.combine.setCurrentIndex(max(self.combine.findData(spec.get("combine", "worst")), 0))
            values = spec.get("values", ())
            self.nominal.setValue(int(spec.get("nominal", len(values) // 2)))
            self.sharpness.setValue(float(spec.get("sharpness", 50.0)))
        self._on_enabled(bool(spec))
