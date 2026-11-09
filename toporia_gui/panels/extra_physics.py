# toporia_gui/panels/extra_physics.py — more physics on the same design (To do item 9).
#
# On the Problem page, under the main physics: each row adds a physics that is solved
# on the same density with its own material law and its own solid and void property.
# Its quantities can then be measured by your own variables ("measures … on …") and so
# become objectives, terms or constraints.

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


def companion_models(main=None):
    """The models that can be an extra physics next to `main`: assembled, same dimensions, not main."""
    from toporia_core.framework.parts.assembled import AssembledModel
    from toporia_core.framework.registries import MODELS
    dims = set(getattr(getattr(main, "physics", None), "dims", (2, 3)))
    return [cls for cls in MODELS.classes()
            if issubclass(cls, AssembledModel) and cls.physics is not None
            and (main is None or cls.name != main.name) and dims & set(getattr(cls.physics, "dims", (2,)))]


def _number(text):
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


class _PhysicsRow(QWidget):
    """One extra physics: model, material law, solid and void property, ✕."""

    changed = Signal()

    def __init__(self, models, spec, on_remove, parent=None):
        from toporia_core.framework.registries import INTERPOLATIONS

        from .specs import _SpecRow
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        top = QHBoxLayout()
        self.model = QComboBox()
        self.set_models(models, spec.get("model"))
        self.E0 = QLineEdit(str(spec["E0"]) if "E0" in spec else "")
        self.E0.setPlaceholderText("solid: auto")
        self.E0.setToolTip("This physics' property of solid material (a conductivity for heat). Empty uses "
                           "the scenario's E0.")
        self.Emin = QLineEdit(str(spec["Emin"]) if "Emin" in spec else "")
        self.Emin.setPlaceholderText("void: auto")
        self.Emin.setToolTip("Its property of void. Empty: the scenario's Emin, or a thousandth of solid "
                             "for heat conduction.")
        remove = QPushButton("✕")
        remove.setFixedWidth(28)
        remove.clicked.connect(lambda: on_remove(self))
        for widget in (self.model, self.E0, self.Emin, remove):
            top.addWidget(widget, 1 if widget is self.model else 0)
        outer.addLayout(top)
        self.material = _SpecRow(INTERPOLATIONS.classes(), spec=spec.get("interpolation") or {"type": "simp"})
        outer.addWidget(self.material)
        self.model.currentIndexChanged.connect(self.changed.emit)
        self.E0.textChanged.connect(self.changed.emit)
        self.Emin.textChanged.connect(self.changed.emit)
        self.material.changed.connect(self.changed.emit)

    def set_models(self, models, wanted=None):
        """Offer these model classes, keeping the chosen one."""
        wanted = wanted or self.model.currentData()
        self.model.blockSignals(True)
        self.model.clear()
        for cls in models:
            self.model.addItem(cls.physics.label, userData=cls.name)
        if wanted is not None and self.model.findData(wanted) < 0:
            self.model.addItem(f"{wanted} (not possible here)", userData=wanted)
        self.model.setCurrentIndex(max(0, self.model.findData(wanted)))
        self.model.blockSignals(False)

    def spec(self):
        """This physics as a spec dict."""
        spec = {"model": self.model.currentData(), "interpolation": self.material.get_spec()}
        for key, edit in (("E0", self.E0), ("Emin", self.Emin)):
            value = _number(edit.text())
            if value is not None:
                spec[key] = value
        return spec


class ExtraPhysicsGroup(QWidget):
    """More physics on the same design field, each with its own material law."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._main = None
        self._rows = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        section = CollapsibleSection("More physics on the same design", expanded=False)
        body = section.body_layout
        note = QLabel("Each is solved on the same density with its own material law. Measure its "
                      "quantities with your own variables (Variables and fields), then use them in "
                      "the objective or as constraints.")
        note.setWordWrap(True)
        body.addWidget(note)
        self._list = QVBoxLayout()
        body.addLayout(self._list)
        self.add_button = QPushButton("+ Add physics")
        self.add_button.clicked.connect(self._add_new)
        body.addWidget(self.add_button)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        outer.addWidget(section)
        self.section = section

    def set_main(self, model_cls):
        """The main physics: the extra ones must differ from it and share its dimensions."""
        self._main = model_cls
        for row in self._rows:
            row.set_models(companion_models(model_cls))
        self._validate()

    def _add_new(self):
        taken = {row.spec()["model"] for row in self._rows}
        free = [cls for cls in companion_models(self._main) if cls.name not in taken]
        if free:
            self._add({"model": free[0].name})

    def _add(self, spec):
        row = _PhysicsRow(companion_models(self._main), spec, self._remove)
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
        """Every extra physics as a spec dict."""
        return [row.spec() for row in self._rows]

    def load_specs(self, specs):
        """Show these extra physics."""
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        for spec in specs or ():
            self._add(dict(spec))
        self._edited()

    def companions(self):
        """[(model name, physics class)] of the extra physics, for the variables panel."""
        from toporia_core.framework.registries import MODELS
        out = []
        for spec in self.get_specs():
            if spec["model"] in MODELS.names():
                out.append((spec["model"], MODELS.get(spec["model"]).physics))
        return out

    def _validate(self):
        from toporia_core.framework.companions import check_extra_physics
        try:
            check_extra_physics(self.get_specs(), self._main)
            self.status.setText("")
        except ValueError as error:
            self.status.setText(f"⚠ {error}")
