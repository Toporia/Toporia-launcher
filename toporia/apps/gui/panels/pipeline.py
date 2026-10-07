# apps/gui/panels/pipeline.py — the Pipeline box: what the selected run is made of.

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QVBoxLayout,
)


class PipelineView(QGroupBox):
    """The selected pipeline, stage by stage, and why any part of it is unavailable.

    It shows what the run will actually do (which filters, which physics,
    which responses, which updater), so swapping one part is visible at once,
    and a hidden panel (no filters, no constraints) is explained, not just gone.
    """

    def __init__(self, parent=None):
        super().__init__("Pipeline", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self._stages = QLabel()
        self._stages.setWordWrap(True)
        self._stages.setTextFormat(Qt.RichText)
        self._notes = QLabel()
        self._notes.setWordWrap(True)
        self._notes.setTextFormat(Qt.RichText)
        layout.addWidget(self._stages)
        layout.addWidget(self._notes)
        self._plain_stages, self._plain_notes = [], []

    def show_pipeline(self, stages, notes):
        """Show [(stage, text), ...] top to bottom, then the notes in grey."""
        self._plain_stages, self._plain_notes = list(stages), list(notes)
        rows = [f"<b>{html.escape(stage)}</b>: {html.escape(text)}" for stage, text in stages]
        self._stages.setText("<br>&nbsp;&nbsp;↓ ".join(rows) + "<br>&nbsp;&nbsp;↺ <i>next design</i>")
        self._notes.setVisible(bool(notes))
        self._notes.setText("<br>".join(f"<span style='color:gray'>• {html.escape(n)}</span>" for n in notes))

    def stages(self):
        """The displayed [(stage, text), ...]."""
        return list(self._plain_stages)

    def notes(self):
        """The displayed notes."""
        return list(self._plain_notes)
