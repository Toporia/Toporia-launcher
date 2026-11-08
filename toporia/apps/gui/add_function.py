# apps/gui/add_function.py — one pop-up with every function that can be added to the method.
#
# The Method step's "+ Add function…" opens it.  An entry that does not fit the current
# selection is greyed out but can still be chosen (choosing it changes what conflicts with
# it); one that nothing in the Method step can make fit is disabled and says why.  Where a
# function could go in more than one place (several optimisations, several groups), the
# dialog asks where.

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class AddFunctionDialog(QDialog):
    """Pick a function, and where it goes; `choice` is (kind, name, place) after Add."""

    def __init__(self, entries, active_stage=None, parent=None):
        super().__init__(parent)
        from .workflow_ui import FIXED
        self.setWindowTitle("Add function")
        self.resize(560, 620)
        self.choice = None
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a function…")
        layout.addWidget(self.search)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        self.reason = QLabel()
        self.reason.setWordWrap(True)
        layout.addWidget(self.reason)
        form = QFormLayout()
        self.place = QComboBox()
        form.addRow("Place in", self.place)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Add")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.add_button = buttons.button(QDialogButtonBox.Ok)
        layout.addWidget(buttons)

        self._active = active_stage
        for label, kind, name, reason, places in entries:
            item = QListWidgetItem(label, self.list)
            item.setData(Qt.UserRole, (kind, name, places, reason))
            if reason and reason.startswith(FIXED):
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setToolTip(f"Unavailable here: {reason}")
            elif reason:
                item.setForeground(self.palette().brush(QPalette.Disabled, QPalette.Text))
                item.setToolTip(f"Does not fit the current selection: {reason}. Choosing it changes the "
                                "parts that conflict with it.")
        self.list.currentItemChanged.connect(lambda *_: self._show_places())
        self.list.itemDoubleClicked.connect(lambda *_: self._accept())
        self.search.textChanged.connect(self._filter)
        self._show_places()

    def _filter(self, text):
        text = text.casefold()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text not in item.text().casefold())

    def _show_places(self):
        item = self.list.currentItem()
        self.place.clear()
        if item is None or not item.flags() & Qt.ItemIsEnabled:
            self.place.setEnabled(False)
            self.add_button.setEnabled(False)
            self.reason.setText("")
            return
        kind, name, places, reason = item.data(Qt.UserRole)
        for label, place in places:
            self.place.addItem(label, place)
        active = next((i for i, (_, place) in enumerate(places) if place == ("stage", self._active)), 0)
        self.place.setCurrentIndex(active)
        self.place.setEnabled(len(places) > 1)              # a choice only where there is one
        self.add_button.setEnabled(bool(places))
        self.reason.setText(f"Does not fit the current selection: {reason}. Adding it changes what conflicts."
                            if reason else "")

    def _accept(self):
        item = self.list.currentItem()
        if item is None or not item.flags() & Qt.ItemIsEnabled or self.place.currentData() is None:
            return
        kind, name, _, _ = item.data(Qt.UserRole)
        self.choice = (kind, name, self.place.currentData())
        self.accept()
