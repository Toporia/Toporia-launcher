# apps/gui/style_maker.py — make your own style from four colours.
#
# Background, surfaces (fields and lists), text and accent are chosen; every other
# chrome colour (borders, hover, disabled text, selection) is derived from them
# (appearance.full_scheme), so any four colours give a consistent style.  Scientific
# colours (supports, loads, result fields) are not part of a style.

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .appearance import SCHEMES, full_scheme, style_sheet

ROLES = (("background", "Background"), ("surface", "Fields and lists"), ("text", "Text"), ("accent", "Accent"))


class StyleMaker(QDialog):
    """Four colour buttons, a starting point, and a live preview; `scheme` after OK."""

    def __init__(self, scheme, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Style maker")
        self.scheme = dict(scheme)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.start = QComboBox()
        self.start.addItem("Keep these colours", None)
        for name in SCHEMES:
            self.start.addItem(f"Start from {name.capitalize()}", name)
        self.start.currentIndexChanged.connect(self._start_from)
        form.addRow("Start", self.start)
        self.buttons = {}
        for key, label in ROLES:
            button = QPushButton()
            button.setMinimumWidth(160)
            button.clicked.connect(lambda _=False, k=key: self._pick(k))
            self.buttons[key] = button
            form.addRow(label, button)
        layout.addLayout(form)
        self.preview = QFrame()
        self.preview.setFrameShape(QFrame.StyledPanel)
        box = QVBoxLayout(self.preview)
        box.addWidget(QLabel("<b>Preview</b> · a project's settings look like this"))
        row = QHBoxLayout()
        row.addWidget(QPushButton("A button"))
        field = QLineEdit("A field")
        row.addWidget(field)
        check = QCheckBox("An option")
        check.setChecked(True)
        row.addWidget(check)
        box.addLayout(row)
        disabled = QPushButton("Not available")
        disabled.setEnabled(False)
        box.addWidget(disabled)
        layout.addWidget(self.preview)
        done = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        done.button(QDialogButtonBox.Ok).setText("Use this style")
        done.accepted.connect(self.accept)
        done.rejected.connect(self.reject)
        layout.addWidget(done)
        self._refresh()

    def _start_from(self, index):
        name = self.start.itemData(index)
        if name is not None:
            self.scheme = dict(SCHEMES[name])
            self._refresh()

    def _pick(self, key):
        colour = QColorDialog.getColor(QColor(self.scheme[key]), self, f"Choose: {dict(ROLES)[key]}")
        if colour.isValid():
            self.set_colour(key, colour.name())

    def set_colour(self, key, value):
        self.scheme[key] = QColor(value).name()
        self._refresh()

    def _refresh(self):
        for key, button in self.buttons.items():
            value = self.scheme[key]
            text = "#000000" if QColor(value).lightnessF() > 0.5 else "#ffffff"
            button.setText(value)
            button.setStyleSheet(f"background: {value}; color: {text}; border: 1px solid #888888;")
        self.preview.setStyleSheet(style_sheet(full_scheme(self.scheme)))
