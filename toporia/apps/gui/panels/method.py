# apps/gui/panels/method.py — the core parameters and the method, chosen part by part.
#
# CoreParamsGroup holds the mesh resolution and volume fraction, then the
# method — a physics model and an updater (any pair), or a whole method —
# each with its own generated parameter form, then convergence and output.


from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

from .common import (
    CollapsibleSection,
    add_tooltip_row,
    mark_availability,
)
from .forms import ParamForm


class CoreParamsGroup(QWidget):
    """Scenario fields, the optimisation method as explicit parts, and convergence/output.

    The method is chosen part by part: a physics model and an updater, any
    pair of them — or a whole method that does not split into parts (the RBF
    level set).  Each part shows its own parameters.  Every input is generated
    from Param declarations and the plugin registries, so a new model, updater
    or method appears here without editing this file.
    """
    method_changed = Signal(str)   # fires with the method name: "<model>+<updater>" or a whole method

    #: The "Method" selector's entry for a method assembled from a model and an updater.
    PARTS = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        from toporia.framework import OUTPUT_PARAMS, SCENARIO_PARAMS, SOLVER_PARAMS
        from toporia.framework.params import select
        from toporia.plugins.methods import METHODS
        from toporia.plugins.models import MODELS
        from toporia.plugins.updaters import UPDATERS

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        core = QGroupBox("Core Parameters")
        # The mesh resolution lives in the Design section, with 2-D/3-D.
        self._design = ParamForm(select(SCENARIO_PARAMS, "volfrac"))
        QVBoxLayout(core).addWidget(self._design)
        outer.addWidget(core)

        opt = CollapsibleSection("Method", expanded=True)
        selector = QFormLayout()
        self.approach = QComboBox()
        self.approach.addItem("Physics model + updater", userData=self.PARTS)
        for cls in METHODS.classes():
            self.approach.addItem(f"{cls.label} (whole method)", userData=cls.name)
        mark_availability(self.approach, METHODS.classes())
        add_tooltip_row(selector, "Method", self.approach,
                         "Pick a physics model and an updater separately (any pair works), or a whole "
                         "method that brings its own design representation and update.")
        opt.body_layout.addLayout(selector)

        # One selector and one parameter panel per part; whole methods get a panel each.
        self.model, self._model_forms, self._model_row = self._part_selector(
            opt, "Physics model", MODELS.classes(),
            "What is solved: the physics engine, and with it which objectives and constraints "
            "can be computed.")
        self.updater, self._updater_forms, self._updater_row = self._part_selector(
            opt, "Updater", UPDATERS.classes(),
            "How the design moves from one iteration to the next.")
        self._method_forms = {}
        for cls in METHODS.classes():
            form = ParamForm(cls.params)
            self._method_forms[cls.name] = form
            opt.body_layout.addWidget(form)
        outer.addWidget(opt)

        self._convergence = ParamForm(select(SOLVER_PARAMS, "max_iter", "tol"))
        self._output = ParamForm(OUTPUT_PARAMS)
        for title, form in (("Convergence", self._convergence), ("Output", self._output)):
            section = CollapsibleSection(title, expanded=False)
            section.body_layout.addWidget(form)
            outer.addWidget(section)

        for combo in (self.approach, self.model, self.updater):
            combo.currentIndexChanged.connect(self._on_method_changed)
        self._on_method_changed()

    @staticmethod
    def _part_selector(section, title, classes, tooltip):
        """A titled selector for one part, with that part's parameter panel under it."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        row = QFormLayout()
        combo = QComboBox()
        add_tooltip_row(row, title, combo, tooltip)
        layout.addLayout(row)
        forms = {}
        for cls in classes:
            combo.addItem(cls.label, userData=cls.name)
            forms[cls.name] = ParamForm(cls.params)
            layout.addWidget(forms[cls.name])
        mark_availability(combo, classes)
        section.body_layout.addWidget(box)
        return combo, forms, box

    def _composed(self):
        return self.approach.currentData() == self.PARTS

    def method_name(self):
        """The selected method: "<model>+<updater>", or a whole method's name."""
        from toporia.framework.parts.composition import SEPARATOR
        if self._composed():
            return f"{self.model.currentData()}{SEPARATOR}{self.updater.currentData()}"
        return self.approach.currentData()

    def select_method(self, name):
        """Show the method `name`, in either form; older names such as "density" are accepted."""
        from toporia.framework.parts.composition import ComposedMethod
        from toporia.plugins.methods import method_class
        cls = method_class(name)
        combos = (self.approach, self.model, self.updater)
        for combo in combos:
            combo.blockSignals(True)
        if issubclass(cls, ComposedMethod):
            self.approach.setCurrentIndex(self.approach.findData(self.PARTS))
            self.model.setCurrentIndex(self.model.findData(cls.model.name))
            self.updater.setCurrentIndex(self.updater.findData(cls.updater.name))
        else:
            self.approach.setCurrentIndex(self.approach.findData(cls.name))
        for combo in combos:
            combo.blockSignals(False)
        self._on_method_changed()

    def _all_forms(self):
        return [*self._model_forms.values(), *self._updater_forms.values(), *self._method_forms.values()]

    def _visible_forms(self):
        if self._composed():
            return [self._model_forms[self.model.currentData()], self._updater_forms[self.updater.currentData()]]
        return [self._method_forms[self.approach.currentData()]]

    def _on_method_changed(self, *_):
        composed = self._composed()
        self._model_row.setVisible(composed)
        self._updater_row.setVisible(composed)
        visible = self._visible_forms()
        for form in self._all_forms():
            form.setVisible(form in visible)
        self.method_changed.emit(self.method_name())

    def get_kwargs(self):
        """Return {field: value} to overlay on a Run with Run.updated."""
        method_params = {}
        for form in self._visible_forms():
            method_params.update(form.get_values())
        return {
            **self._design.get_values(),
            **self._convergence.get_values(),
            **self._output.get_values(),
            "method": self.method_name(),
            "method_params": method_params,
        }

    def load_from_config(self, cfg):
        """Populate every panel from a Run (called when a preset is selected)."""
        from toporia.framework import read_param
        self.select_method(cfg.solver.method)
        visible = self._visible_forms()
        for form in self._all_forms():
            mine = {k: v for k, v in cfg.solver.method_params.items() if k in form.names()}
            form.set_values(mine if form in visible else {})
        for form in (self._design, self._convergence, self._output):
            form.set_values({key: read_param(cfg, key) for key in form.names()})
