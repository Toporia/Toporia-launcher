# gui/param_form.py — build input widgets from Param declarations.
#
# This is the only place that knows how to turn a core.params.Param into a Qt
# widget.  Every method, filter and scenario panel in the GUI is a ParamForm,
# so adding a parameter to a plugin makes it appear here with no GUI changes.

from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QSpinBox, QWidget

_UNBOUNDED = 1e9   # spin boxes need finite limits; used when a Param has none


class ParamForm(QWidget):
    """A form with one row per Param.  Values go in and out as plain dicts."""

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self._params = tuple(params)
        self._editors = {}
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        for param in self._params:
            editor = _make_editor(param)
            label = QLabel(f"{param.label} [{param.units}]" if param.units else param.label)
            if param.help:
                label.setToolTip(param.help)
                editor.setToolTip(param.help)
            form.addRow(label, editor)
            self._editors[param.name] = editor
        self.set_values({})

    def names(self):
        """The parameter names shown in this form, in display order."""
        return [param.name for param in self._params]

    def get_values(self):
        """Return {name: value} for every parameter in the form."""
        return {param.name: _read(self._editors[param.name], param) for param in self._params}

    def set_values(self, values):
        """Show `values`; any parameter not in the dict is reset to its default."""
        for param in self._params:
            _write(self._editors[param.name], param, values.get(param.name, param.default))


def _make_editor(param):
    if param.kind == "bool":
        return QCheckBox()
    if param.kind == "choice":
        box = QComboBox()
        for value, text in param.choices:
            box.addItem(text, userData=value)
        return box
    low = param.min if param.min is not None else -_UNBOUNDED
    high = param.max if param.max is not None else _UNBOUNDED
    if param.kind == "int":
        box = QSpinBox()
        box.setRange(int(low), int(high))
        box.setSingleStep(int(param.step or 1))
        return box
    box = QDoubleSpinBox()
    box.setDecimals(param.decimals if param.decimals is not None else 3)
    box.setRange(low, high)
    box.setSingleStep(param.step or 0.1)
    return box


def _read(editor, param):
    if param.kind == "bool":
        return editor.isChecked()
    if param.kind == "choice":
        return editor.currentData()
    return editor.value()


def _write(editor, param, value):
    value = param.coerce(value)
    if param.kind == "bool":
        editor.setChecked(value)
    elif param.kind == "choice":
        editor.setCurrentIndex(max(editor.findData(value), 0))
    else:
        editor.setValue(value)
