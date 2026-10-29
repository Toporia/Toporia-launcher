"""Progressive, resumable setup for a deliberately empty custom problem."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from toporia.framework.registry import missing_dependencies
from toporia.plugins.methods import method_class
from toporia.plugins.models import MODELS
from toporia.plugins.representations import REPRESENTATIONS
from toporia.plugins.responses import RESPONSES


class _Number(QDoubleSpinBox):
    """Keep precise input without padding every value with six zeroes."""

    def textFromValue(self, value):
        text = super().textFromValue(value)
        separator = self.locale().decimalPoint()
        return text.rstrip("0").rstrip(separator) if separator in text else text


class BlankSetup(QScrollArea):
    """Collect explicit choices before exposing the geometry editor or solver controls."""

    changed = Signal(dict)
    completed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        body = QWidget()
        body.setMaximumWidth(760)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(32, 24, 32, 24)
        title = QLabel("Start with an empty problem")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)
        intro = QLabel("Choose how to describe your design space. Each choice reveals the next part. "
                       "You can save this setup at any time.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.groups, self.fields = {}, {}
        self.dimension = self._choice(layout, "dimension", "1 · Dimensions", "Choose dimensions…")
        self.dimension.addItem("2D", 2)
        self.dimension.addItem("3D", 3)
        self.representation = self._choice(layout, "representation", "2 · Representation", "Choose a representation…")
        domain = self._group(layout, "domain", "3 · Design space and resolution")
        for key, label, maximum in (("Lx", "Width [mm]", 10000), ("Ly", "Height [mm]", 10000),
                                    ("Lz", "Depth [mm]", 10000), ("element_size", "Element size [mm]", 1000)):
            self._number(domain, key, label, 0, maximum)
        self.fields["Lz"].setDecimals(2)
        self.fields["Lz"].setToolTip("Depth must be at least 0.1 mm.")
        self.fields["element_size"].setToolTip("Element size must be at least 0.001 mm.")
        self.mesh = QLabel()
        self.mesh.setWordWrap(True)
        domain.addRow(self.mesh)
        self.physics = self._choice(layout, "physics", "4 · Physics and material", "Choose physics…")
        material = self.groups["physics"].layout()
        self._number(material, "E0", "Young's modulus [N/mm²]", 0, 1e7)
        self._number(material, "nu", "Poisson ratio", -.99, .499)
        self.objective = self._choice(layout, "objective", "5 · Objective and budget", "Choose an objective…")
        self._number(self.groups["objective"].layout(), "volfrac", "Maximum volume fraction [0–1]", 0, 1)
        self.fields["volfrac"].setDecimals(3)
        self.fields["volfrac"].setToolTip("Choose a fraction from 0.01 to 1.")
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self.create = QPushButton("Create design space")
        self.create.setMinimumHeight(40)
        self.create.clicked.connect(lambda: self.completed.emit(self.values()))
        layout.addWidget(self.create)
        layout.addStretch()
        self.setWidget(body)
        self._loading = False
        self.dimension.currentIndexChanged.connect(self._dimension_changed)
        self.representation.currentIndexChanged.connect(self._representation_changed)
        self.physics.currentIndexChanged.connect(self._physics_changed)
        self.objective.currentIndexChanged.connect(self._update)
        for field in self.fields.values():
            field.valueChanged.connect(self._update)
        self.load({})

    def _group(self, layout, key, title):
        group = QGroupBox(title)
        form = QFormLayout(group)
        layout.addWidget(group)
        self.groups[key] = group
        return form

    def _choice(self, layout, key, title, placeholder):
        form = self._group(layout, key, title)
        combo = QComboBox()
        combo.addItem(placeholder, None)
        form.addRow(combo)
        return combo

    def _number(self, form, key, label, minimum, maximum):
        field = _Number()
        field.setDecimals(6)
        field.setRange(minimum, maximum)
        field.setSpecialValueText("Enter a value…")
        field.setValue(minimum)
        field.setKeyboardTracking(False)
        form.addRow(label, field)
        self.fields[key] = field

    def values(self):
        """Small plain-data draft, independent of solver defaults and results."""
        return {"dimension": self.dimension.currentData(), "representation": self.representation.currentData(),
                "physics": self.physics.currentData(), "objective": self.objective.currentData(),
                **{key: field.value() for key, field in self.fields.items()}}

    def load(self, state):
        """Restore a partial draft without accepting previously unchosen defaults."""
        self._loading = True
        self.dimension.setCurrentIndex(max(0, self.dimension.findData(state.get("dimension"))))
        self._representations()
        self.representation.setCurrentIndex(max(0, self.representation.findData(state.get("representation"))))
        self._models()
        self.physics.setCurrentIndex(max(0, self.physics.findData(state.get("physics"))))
        self._objectives()
        self.objective.setCurrentIndex(max(0, self.objective.findData(state.get("objective"))))
        for key, field in self.fields.items():
            field.setValue(state.get(key, field.minimum()))
        self._loading = False
        self._update()

    def _fill(self, combo, entries):
        blocked = combo.blockSignals(True)
        while combo.count() > 1:
            combo.removeItem(1)
        for label, name in entries:
            combo.addItem(label, name)
        combo.setCurrentIndex(0)
        combo.blockSignals(blocked)

    def _representations(self):
        dim = self.dimension.currentData()
        self._fill(self.representation, [(r.label, r.name) for r in REPRESENTATIONS.classes()
                                        if r.dims is None or dim in r.dims])

    def _models(self):
        dim = self.dimension.currentData()
        self._fill(self.physics, [(m.label, m.name) for m in MODELS.classes()
                                 if dim in m.capabilities.dims and m.capabilities.accepts_representation
                                 and not missing_dependencies(m)])

    def _objectives(self):
        model = self.physics.currentData()
        names = method_class(self.method_name()).capabilities.objectives if model else ()
        self._fill(self.objective, [(RESPONSES.get(name).label, name) for name in names])

    def method_name(self):
        """Use a compatible starting updater; Method remains editable afterward."""
        rep = self.representation.currentData()
        updater = "oc" if rep and REPRESENTATIONS.get(rep).element_wise else "mma"
        return f"{self.physics.currentData()}+{updater}"

    def _dimension_changed(self):
        if self._loading:
            return
        self._representations()
        self._models()
        self._objectives()
        self._update()

    def _representation_changed(self):
        if self._loading:
            return
        self._models()
        self._objectives()
        self._update()

    def _physics_changed(self):
        if not self._loading:
            self._objectives()
            self._update()

    def _update(self):
        if self._loading:
            return
        state = self.values()
        dim, rep = state["dimension"], state["representation"]
        self.groups["representation"].setVisible(dim is not None)
        self.groups["domain"].setVisible(rep is not None)
        form = self.groups["domain"].layout()
        form.setRowVisible(self.fields["Lz"], dim == 3)
        sizes = [state[k] for k in (("Lx", "Ly", "Lz") if dim == 3 else ("Lx", "Ly"))]
        domain_ready = (rep is not None and all(s > 0 for s in sizes) and state["element_size"] >= .001
                        and (dim != 3 or state["Lz"] >= .1))
        counts = [round(s / state["element_size"]) for s in sizes] if domain_ready else []
        mesh_ready = bool(counts) and all(n > 0 for n in counts)
        self.mesh.setText(" × ".join(map(str, counts)) + " elements" if mesh_ready else
                          "Enter sizes and a resolution that gives at least one element in each direction.")
        self.groups["physics"].setVisible(mesh_ready)
        physics_ready = mesh_ready and state["physics"] is not None and state["E0"] > 0 and state["nu"] > -.99
        self.groups["objective"].setVisible(physics_ready)
        ready = physics_ready and state["objective"] is not None and state["volfrac"] >= .01
        self.create.setEnabled(ready)
        if dim is None:
            message = "Choose 2D or 3D to begin."
        elif rep is None:
            message = "Choose how the design is represented."
        elif not mesh_ready:
            message = "Enter the design-space sizes and element size (at least 0.001 mm; 3D depth at least 0.1 mm)."
        elif not physics_ready:
            message = "Choose physics and enter Young's modulus and Poisson ratio."
        elif not ready:
            message = "Choose an objective and a volume fraction from 0.01 to 1."
        else:
            message = "Ready to create an empty design space. Add your supports and loads in the editor next."
        self.feedback.setText(message)
        self.changed.emit(state)
