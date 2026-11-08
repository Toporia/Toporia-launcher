# apps/gui/run_window.py — a run in its own window, so the main window stays usable.
#
# The run works on a snapshot of the project saved when it starts, so the problem and
# the method may be edited while it runs.  The live view (status, progress, the design
# and its curve, the console) moves into this window for the run and goes back to the
# Runner step when the window is closed.

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget


class RunWindow(QWidget):
    """Holds the Runner step's live widgets while a run is shown on its own."""

    stop_requested = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Toporia — run")
        self.resize(1000, 720)
        self.body = QVBoxLayout(self)
        buttons = QHBoxLayout()
        self.stop_button = QPushButton("Stop")
        self.stop_button.setToolTip("Stop at the end of the current iteration; the design so far is kept.")
        self.stop_button.clicked.connect(self.stop_requested.emit)
        buttons.addWidget(self.stop_button)
        buttons.addStretch(1)
        self.body.addLayout(buttons)
        self._borrowed = []          # (widget, layout it came from, index, stretch)

    def borrow(self, widgets):
        """Move `widgets` (status, progress, view) here, remembering where each came from."""
        for widget, stretch in widgets:
            layout = widget.parentWidget().layout()
            index = layout.indexOf(widget)
            layout.removeWidget(widget)
            self._borrowed.append((widget, layout, index, stretch))
            self.body.addWidget(widget, stretch)
            widget.show()

    def give_back(self):
        """Return every borrowed widget to its place in the Runner step."""
        for widget, layout, index, stretch in reversed(self._borrowed):
            self.body.removeWidget(widget)
            layout.insertWidget(index, widget, stretch)
            widget.show()
        self._borrowed = []

    def set_running(self, running, status=""):
        self.stop_button.setEnabled(running)
        self.setWindowTitle("Toporia — running" if running else f"Toporia — {status.lower() or 'run'}")

    def closeEvent(self, event):
        if self.stop_button.isEnabled():          # still running: closing would hide the only Stop
            self.showMinimized()
            event.ignore()
            return
        self.give_back()
        self.closed.emit()
        super().closeEvent(event)
