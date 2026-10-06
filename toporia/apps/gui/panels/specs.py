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
    QLabel,
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

    changed = Signal()  # the selected type changed

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
            remove = QPushButton("✕")
            remove.setFixedWidth(28)
            remove.clicked.connect(lambda: on_remove(self))
            header.addWidget(remove)
        outer.addLayout(header)

        self._wanted = self._classes[0].name if self._classes else None  # kept while it is not offered
        self._forms = {}
        for cls in self._classes:
            self._forms[cls.name] = ParamForm(cls.params, self)
            outer.addWidget(self._forms[cls.name])
        self._fill_types([cls.name for cls in self._classes])

        if spec:
            self.load_spec(spec)
        self._type.currentIndexChanged.connect(self._on_chosen)
        self._on_type_changed()

        if on_remove is not None:
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            outer.addWidget(line)

    def _fill_types(self, names):
        # The type chosen last is remembered, not the one shown: while a method
        # allows no type at all the row is empty, and switching back must restore it.
        self._type.blockSignals(True)
        self._type.clear()
        for cls in self._classes:
            if cls.name in names:
                self._type.addItem(cls.label, userData=cls.name)
        mark_availability(self._type, self._classes)
        self._type.setCurrentIndex(max(self._type.findData(self._wanted), 0))
        self._type.blockSignals(False)

    def _on_chosen(self, *_):
        """The person picked a type (refills block this signal, so a fallback never counts)."""
        if self._type.currentData() is not None:
            self._wanted = self._type.currentData()
        self._on_type_changed()

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
        key = self._type.currentData() or self._wanted
        return {"type": key, **self._forms[key].get_values()}

    def load_spec(self, spec):
        values = dict(spec)
        key = values.pop("type", self._classes[0].name)
        if key in self._forms:
            self._wanted = key
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

    changed = Signal()  # a row was added or removed, or changed type

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
        add = self._add = QPushButton(f"+ Add {noun}")
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

    def _make_row(self, spec):
        return _SpecRow(self._classes, on_remove=self._remove_row, parent=self._rows_container, spec=spec)

    def _add_row(self, spec=None):
        row = self._make_row(spec)
        row.set_allowed(self._allowed)
        row.changed.connect(self.changed.emit)
        self._rows.append(row)
        self._rows_box.addWidget(row)
        self._refresh_label()
        self.changed.emit()

    def _remove_row(self, row):
        self._rows.remove(row)
        self._rows_box.removeWidget(row)
        row.hide()  # disappear now; Qt frees it on the next event-loop pass
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


class ConstraintsGroup(SpecListGroup):
    """The optimisation constraints, always shown: the volume budget, and the limits on top of it.

    The volume budget (Vol fraction) is enforced by every method.  Further
    constraints — a stress limit, say — need a method that can enforce them;
    with one that cannot, the section stays in view, keeps its rows for later,
    and says why and which updaters can, instead of disappearing.
    """

    def __init__(self, classes, parent=None):
        super().__init__("Constraints", classes, noun="constraint", parent=parent)
        layout = self._body.layout()
        budget = QLabel("Volume budget: always enforced (Vol fraction, in Core Parameters).")
        budget.setWordWrap(True)
        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setStyleSheet("color: #a05a00;")
        layout.insertWidget(0, budget)
        layout.insertWidget(1, self._note)
        self._note.hide()
        self._reason = ""

    def available(self):
        """Whether the selected method can enforce any constraint besides the volume budget."""
        return bool(self._allowed)

    def set_allowed(self, names, reason=""):
        """Offer these types; with none, keep the section visible, its rows inactive, and say why."""
        self._allowed = list(names)
        for row in self._rows:
            row.set_allowed(self._allowed)
        self._rows_container.setEnabled(bool(self._allowed))
        self._add.setEnabled(bool(self._allowed))
        self._reason = "" if self._allowed else reason
        self._note.setText(self._reason)
        self._note.setVisible(bool(self._reason))
        self._refresh_label()
        self.changed.emit()

    def _refresh_label(self):
        super()._refresh_label()
        if getattr(self, "_allowed", True) == [] and self._rows:
            self._toggle.setText(self._toggle.text().replace("active)", "kept, not enforced by this method)"))


class _ScheduleRow(_SpecRow):
    """A schedule: which parameter it drives, then the schedule type and its values."""

    def __init__(self, classes, paths, on_remove=None, parent=None, spec=None):
        super().__init__(classes, on_remove=on_remove, parent=parent)
        self._path = QComboBox()
        self._path.setToolTip(
            "The parameter this schedule changes during the run. Only parameters "
            "their part allows to change mid-run are offered."
        )
        self.layout().insertWidget(0, self._path)
        self.set_paths(paths)
        if spec:
            self.load_spec(spec)
        self._path.currentIndexChanged.connect(lambda *_: self.changed.emit())

    def set_paths(self, items):
        """Offer these (label, path) items; a path set before stays, marked, when it is no longer offered."""
        current = self._path.currentData()
        self._path.blockSignals(True)
        self._path.clear()
        for label, path in items:
            self._path.addItem(label, userData=path)
        if current and self._path.findData(current) < 0:
            self._path.addItem(f"{current} (not changeable with this setup)", userData=current)
        self._path.setCurrentIndex(max(self._path.findData(current), 0))
        self._path.blockSignals(False)

    def get_spec(self):
        return {"path": self._path.currentData(), **super().get_spec()}

    def load_spec(self, spec):
        values = dict(spec)
        path = values.pop("path", None)
        if path is not None and hasattr(self, "_path"):
            if self._path.findData(path) < 0:
                self._path.addItem(path, userData=path)
            self._path.setCurrentIndex(self._path.findData(path))
        super().load_spec(values)


class ScheduleListGroup(SpecListGroup):
    """Continuation schedules: each drives one parameter during the run (framework/parts/schedule.py).

    The parameter choices follow the method, the filters and the material
    law; with nothing that can change in this setup the group hides.
    """

    def __init__(self, classes, parent=None):
        self._paths = []
        super().__init__("Schedules", classes, noun="schedule", parent=parent)

    def _make_row(self, spec):
        return _ScheduleRow(
            self._classes, self._paths, on_remove=self._remove_row, parent=self._rows_container, spec=spec
        )

    def set_paths(self, items):
        """The parameters the rows may drive, as (label, path); hide the group when there are none."""
        self._paths = list(items)
        for row in self._rows:
            row.set_paths(self._paths)
        allowed = [cls.name for cls in self._classes] if self._paths else []
        if allowed != self._allowed:
            self.set_allowed(allowed)


class SingleSpecGroup(QWidget):
    """One spec row in a titled, folding section: the objective, the material law, the design representation."""

    changed = Signal()
    title = ""

    def __init__(self, classes, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        section = CollapsibleSection(self.title, expanded=False)
        self._row = _SpecRow(classes)
        self._row.changed.connect(self.changed.emit)
        section.body_layout.addWidget(self._row)
        outer.addWidget(section)

    def offered_types(self):
        """The types the selector offers, in menu order."""
        return self._row.offered_types()

    def set_allowed(self, names):
        """Offer only these types."""
        self._row.set_allowed(names)

    def get_spec(self):
        """The row as a spec dict: {"type": ..., <param>: <value>}."""
        return self._row.get_spec()

    def load_spec(self, spec):
        """Show a spec dict in the row."""
        self._row.load_spec(spec)


class ObjectiveGroup(SingleSpecGroup):
    """What the scenario minimises, from the response declarations."""

    title = "Objective"


class MaterialGroup(SingleSpecGroup):
    """The material law (SIMP, RAMP, ...), from the interpolation declarations.

    Hidden when the selected method brings its own (the pyMOTO model) or has
    none (the level set); the Pipeline box then says "Material: inside the model".
    """

    title = "Material law"


class RepresentationGroup(SingleSpecGroup):
    """What the design variables are (element densities, moving morphable components, ...).

    Hidden when the selected method keeps its own variables (the pyMOTO model,
    the level set); the Pipeline box then names the design it uses.
    """

    title = "Design representation"
