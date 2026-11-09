# apps/gui/panels/objective_terms.py — the terms of a combined objective (To do item 4).
#
# Shown under the objective when "Combined objective" is chosen: one row per term
# (which quantity, its name in a formula, its weight, minimise or maximise) and, for
# "Combine by: Python expression", the formula, checked as it is typed.  A term keeps
# the parameters it was loaded with (e.g. a p-norm exponent); new terms use defaults.

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

DEFAULT_TERMS = ({"type": "compliance", "weight": 1.0}, {"type": "volume", "weight": 0.5})


class _TermRow(QWidget):
    """One term: quantity, name, weight, sense, ✕."""

    changed = Signal()

    def __init__(self, classes, spec, on_remove, variable_names=(), parent=None):
        super().__init__(parent)
        self._extra = {k: v for k, v in spec.items() if k not in ("type", "name", "weight", "sense", "variable")}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.kind = QComboBox()
        for cls in classes:
            self.kind.addItem(cls.label, userData=cls.name)
        self.kind.setCurrentIndex(max(0, self.kind.findData(spec.get("type"))))
        self.kind.setToolTip("The quantity this term measures.")
        self.variable = QComboBox()
        self.variable.setEditable(True)
        self.variable.setToolTip("Which variable of the problem (Problem page, Variables and fields).")
        self.variable.addItems(list(variable_names))
        self.variable.setCurrentText(spec.get("variable", ""))
        self.name = QLineEdit(spec.get("name", ""))
        self.name.setPlaceholderText("name")
        self.name.setFixedWidth(90)
        self.name.setToolTip("Its name in a formula; empty uses the quantity's own name.")
        self.weight = QDoubleSpinBox()
        self.weight.setRange(0.0, 1e6)
        self.weight.setDecimals(3)
        self.weight.setSingleStep(0.1)
        self.weight.setValue(float(spec.get("weight", 1.0)))
        self.weight.setToolTip("How much this term counts. Each term is divided by its value at the "
                               "start, so weights compare quantities in different units fairly.")
        self.sense = QComboBox()
        self.sense.addItem("minimise", userData="min")
        self.sense.addItem("maximise", userData="max")
        self.sense.setCurrentIndex(1 if spec.get("sense") == "max" else 0)
        remove = QPushButton("✕")
        remove.setFixedWidth(28)
        remove.clicked.connect(lambda: on_remove(self))
        for widget in (self.kind, self.variable, self.name, self.weight, self.sense, remove):
            layout.addWidget(widget, 1 if widget in (self.kind, self.variable) else 0)
        self.variable.setVisible(self.kind.currentData() == "variable")
        self.variable.currentTextChanged.connect(lambda *_: self.changed.emit())
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.name.textChanged.connect(self.changed.emit)
        self.weight.valueChanged.connect(self.changed.emit)
        self.sense.currentIndexChanged.connect(self.changed.emit)

    def _kind_changed(self):
        self._extra = {}          # parameters of the previous quantity do not apply to this one
        self.variable.setVisible(self.kind.currentData() == "variable")
        self.changed.emit()

    def set_variable_names(self, names):
        """Offer these variable names, keeping the one chosen."""
        current = self.variable.currentText()
        self.variable.blockSignals(True)
        self.variable.clear()
        self.variable.addItems(list(names))
        self.variable.setCurrentText(current)
        self.variable.blockSignals(False)

    def set_offered(self, names):
        """Grey out the quantities the current physics cannot compute."""
        model = self.kind.model()
        for i in range(self.kind.count()):
            item = model.item(i)
            allowed = self.kind.itemData(i) in names
            item.setEnabled(allowed)
            item.setToolTip("" if allowed else "Not available with the current physics and method")

    def spec(self):
        """This term as a spec dict."""
        spec = {"type": self.kind.currentData(), **self._extra, "weight": self.weight.value()}
        if spec["type"] == "variable":
            spec["variable"] = self.variable.currentText().strip()
        if self.sense.currentData() == "max":
            spec["sense"] = "max"
        if self.name.text().strip():
            spec["name"] = self.name.text().strip()
        return spec


class ObjectiveTermsEditor(QWidget):
    """The terms and the formula of a combined objective."""

    changed = Signal()

    def __init__(self, classes, parent=None):
        super().__init__(parent)
        self._classes = [cls for cls in classes if cls.name != "combined"]
        self._offered = {cls.name for cls in self._classes}
        self._rows = []
        self._variable_names = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(QLabel("Terms"))
        self._list = QVBoxLayout()
        layout.addLayout(self._list)
        add = QPushButton("+ Add term")
        add.clicked.connect(lambda: self._add({"type": self._first_offered()}))
        layout.addWidget(add)
        self._expression_label = QLabel("Expression (minimised)")
        self.expression = QLineEdit()
        self.expression.setPlaceholderText("e.g. compliance * sqrt(peak_stress)")
        self.expression.setToolTip("A Python formula of the terms' names: + - * / **, numbers, and sqrt, "
                                   "exp, log, abs, min, max, sin, cos, tanh. It uses the raw values; "
                                   "weights and senses do not apply.")
        self.status = QLabel("")
        self.status.setWordWrap(True)
        for widget in (self._expression_label, self.expression, self.status):
            layout.addWidget(widget)
        self.expression.textChanged.connect(self._edited)
        self._combine = "sum"
        self.load(list(DEFAULT_TERMS), "")

    def _first_offered(self):
        return next((cls.name for cls in self._classes if cls.name in self._offered), self._classes[0].name)

    def _add(self, spec):
        row = _TermRow(self._classes, spec, self._remove, self._variable_names)
        row.set_offered(self._offered)
        row.changed.connect(self._edited)
        self._rows.append(row)
        self._list.addWidget(row)
        self._edited()

    def _remove(self, row):
        if len(self._rows) == 1:
            return               # a combined objective keeps at least one term
        self._rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._edited()

    def _edited(self):
        self._validate()
        self.changed.emit()

    def set_combine(self, combine):
        """Show the formula only when the terms are combined by an expression."""
        self._combine = combine
        for widget in (self._expression_label, self.expression):
            widget.setVisible(combine == "expression")
        self._validate()

    def set_offered(self, names):
        """The quantities the current physics and method can compute."""
        self._offered = set(names)
        for row in self._rows:
            row.set_offered(self._offered)
        self._validate()

    def set_variable_names(self, names):
        """The variables a term may name."""
        self._variable_names = list(names)
        for row in self._rows:
            row.set_variable_names(self._variable_names)
        self._validate()

    def terms(self):
        """Every term as a spec dict."""
        return [row.spec() for row in self._rows]

    def load(self, terms, expression):
        """Show these terms and this formula."""
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        for spec in terms or DEFAULT_TERMS:
            self._add(dict(spec))
        self.expression.blockSignals(True)
        self.expression.setText(expression or "")
        self.expression.blockSignals(False)
        self._validate()

    def _validate(self):
        """Say what is wrong, in words, before a run is started."""
        from toporia_library.responses.combined import compile_expression, term_names
        terms = self.terms()
        problems = [f"{t['type']} is not available here" for t in terms if t["type"] not in self._offered]
        if self._combine == "expression":
            try:
                compile_expression(self.expression.text() or "", term_names(terms))
            except ValueError as error:
                problems.append(str(error))
        names = ", ".join(term_names(terms))
        self.status.setText("⚠ " + "; ".join(problems) if problems else f"Names in a formula: {names}")
