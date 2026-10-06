# apps/gui/panels/specs.py — typed rows: the filter pipeline, the objective, the constraints.
#
# A filter, an objective and a constraint are all a spec of the same shape,
# {"type": <plugin name>, <param>: <value>, ...}, so one row widget serves all
# three.  Rows are generated from the plugin classes (name, label, params), so
# a new filter or response appears here without editing this file.


from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .common import (
    CollapsibleSection,
    mark_availability,
)
from .forms import ParamForm


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
        mark_availability(self._type, self._classes)
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
        section = CollapsibleSection("Objective", expanded=False)
        self._row = _SpecRow(classes)
        self._row.changed.connect(self.changed.emit)
        section.body_layout.addWidget(self._row)
        outer.addWidget(section)

    def offered_types(self):  return self._row.offered_types()
    def set_allowed(self, names): self._row.set_allowed(names)
    def get_spec(self):       return self._row.get_spec()
    def load_spec(self, spec):    self._row.load_spec(spec)
