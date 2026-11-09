# apps/gui/panels/variables.py — the Problem page's variable space (To do items 1 + 2).
#
# Lists every variable of the problem: the quantities the current physics computes
# (built in), your own variables (a measured quantity under a name of your choice, or a
# formula of other variables), and the fields the Post-process page can show.  Your own
# variables are saved with the scenario, recorded every iteration, and can be chosen as
# the objective, a term of a combined objective or a constraint ("A variable of the problem").

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .common import CollapsibleSection

FIELD_FEATURES = (("stress", "von Mises stress"), ("elastic_energy", "strain energy"),
                  ("elastic_energy", "displacement"), ("thermal_energy", "temperature"))


def field_names(physics):
    """The fields of a finished design the Post-process page can show on `physics`."""
    provides = set(getattr(physics, "provides", ()) or ())
    names = ["density"]
    for feature, label in FIELD_FEATURES:
        if feature in provides and label not in names:
            names.append(label)
    return names


class _VariableRow(QWidget):
    """One of your own variables: name, measured quantity or formula, ✕."""

    changed = Signal()

    def __init__(self, quantities, spec, on_remove, parent=None):
        super().__init__(parent)
        self._extra = {k: v for k, v in spec.items() if k not in ("name", "type", "expression", "physics")}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.name = QLineEdit(spec.get("name", ""))
        self.name.setPlaceholderText("name")
        self.name.setFixedWidth(90)
        self.kind = QComboBox()
        self.kind.addItem("measures", userData="measured")
        self.kind.addItem("formula", userData="derived")
        self.quantity = QComboBox()
        wanted = f"{spec['physics']}:{spec['type']}" if spec.get("physics") and spec.get("type") else spec.get("type")
        self.set_quantities(quantities, wanted)
        self.expression = QLineEdit(spec.get("expression", ""))
        self.expression.setPlaceholderText("e.g. compliance * peak_stress / volume")
        self.expression.setToolTip("A Python formula of other variables: + - * / **, numbers, and sqrt, exp, "
                                   "log, abs, min, max, sin, cos, tanh.")
        self.kind.setCurrentIndex(1 if "expression" in spec else 0)
        remove = QPushButton("✕")
        remove.setFixedWidth(28)
        remove.clicked.connect(lambda: on_remove(self))
        for widget in (self.name, self.kind, self.quantity, self.expression, remove):
            layout.addWidget(widget, 1 if widget in (self.quantity, self.expression) else 0)
        self._show_kind()
        self.kind.currentIndexChanged.connect(self._show_kind)
        self.name.textChanged.connect(self.changed.emit)
        self.quantity.currentIndexChanged.connect(self._quantity_changed)
        self.expression.textChanged.connect(self.changed.emit)

    def set_quantities(self, quantities, wanted=None):
        """Offer the built-in quantities [(name, label)] of the current physics."""
        wanted = wanted or self.quantity.currentData()
        self.quantity.blockSignals(True)
        self.quantity.clear()
        for name, label in quantities:
            self.quantity.addItem(label, userData=name)
        if wanted is not None and self.quantity.findData(wanted) < 0:
            self.quantity.addItem(f"{wanted} (not on this physics)", userData=wanted)
        self.quantity.setCurrentIndex(max(0, self.quantity.findData(wanted)))
        self.quantity.blockSignals(False)

    def _quantity_changed(self):
        self._extra = {}
        self.changed.emit()

    def _show_kind(self):
        measured = self.kind.currentData() == "measured"
        self.quantity.setVisible(measured)
        self.expression.setVisible(not measured)
        self.changed.emit()

    def spec(self):
        """This variable as a spec dict."""
        spec = {"name": self.name.text().strip()}
        if self.kind.currentData() == "measured":
            on, _, kind = (self.quantity.currentData() or "").rpartition(":")
            spec.update({"type": kind, **self._extra})
            if on:
                spec["physics"] = on
        else:
            spec["expression"] = self.expression.text().strip()
        return spec


class VariablesGroup(QWidget):
    """Every variable of the problem, built in or your own, and the fields of a design."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._physics = None
        self._quantities = []
        self._companions = []
        self._offered = []
        self._rows = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        section = CollapsibleSection("Variables and fields", expanded=False)
        body = section.body_layout
        self.builtin = QLabel("")
        self.builtin.setWordWrap(True)
        body.addWidget(self.builtin)
        body.addWidget(QLabel("Your own variables (recorded every iteration; choose one as objective or "
                              "constraint with “A variable of the problem”):"))
        self._list = QVBoxLayout()
        body.addLayout(self._list)
        add = QPushButton("+ Add variable")
        add.clicked.connect(self._add_new)
        body.addWidget(add)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        self.fields = QLabel("")
        self.fields.setWordWrap(True)
        body.addWidget(self.fields)
        outer.addWidget(section)
        self.section = section

    def set_physics(self, physics, companions=None):
        """Show what the physics computes, and offer it, and what each extra physics computes, to your variables.

        companions: [(model name, physics class)] of the extra physics on the same design.
        """
        from toporia_core.framework.variables import builtin_quantities
        self._physics = physics
        if companions is not None:
            self._companions = list(companions)
        quantities = builtin_quantities(physics) if physics is not None else {}
        self._quantities = [(name, cls.label) for name, cls in quantities.items()]
        offered = list(self._quantities)
        for model, companion in self._companions:
            offered += [(f"{model}:{name}", f"{cls.label} — on {companion.label}")
                        for name, cls in builtin_quantities(companion).items()]
        self._offered = offered
        built = ", ".join(f"<b>{name}</b> ({label})" for name, label in self._quantities) or "none"
        self.builtin.setText(f"Built in on this physics: {built}")
        fields = ", ".join(field_names(physics)) if physics is not None else "density"
        self.fields.setText(f"Fields of a design (Post-process page): {fields}")
        for row in self._rows:
            row.set_quantities(self._offered)
        self._validate()

    def _add_new(self):
        taken = {row.spec()["name"] for row in self._rows}
        name = next(f"v{i}" for i in range(1, 1000) if f"v{i}" not in taken)
        first = self._quantities[0][0] if self._quantities else "volume"
        self._add({"name": name, "type": first})

    def _add(self, spec):
        row = _VariableRow(self._offered, spec, self._remove)
        row.changed.connect(self._edited)
        self._rows.append(row)
        self._list.addWidget(row)
        self._edited()

    def _remove(self, row):
        self._rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._edited()

    def _edited(self):
        self._validate()
        self.changed.emit()

    def get_specs(self):
        """Your own variables as spec dicts."""
        return [row.spec() for row in self._rows]

    def load_specs(self, specs):
        """Show these variables."""
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        for spec in specs or ():
            self._add(dict(spec))
        self._edited()

    def names(self):
        """Every variable name: built in, then your own."""
        own = [row.spec()["name"] for row in self._rows if row.spec()["name"]]
        return [name for name, _ in self._quantities] + [n for n in own if n not in dict(self._quantities)]

    def _validate(self):
        from toporia_core.framework.variables import check_variables
        try:
            check_variables(self.get_specs(), self._physics)
            self.status.setText("")
        except ValueError as error:
            self.status.setText(f"⚠ {error}")
