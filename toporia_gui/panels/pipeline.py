# apps/gui/panels/pipeline.py — the Pipeline box: what the selected run is made of.
#
# The run is drawn as a network (engine.pipeline.pipeline_graph): one box per
# part, in the order the design flows through them, the responses side by
# side, and an arrow from the updater back to the design for the next
# iteration.  Post-processing hangs below, applied once to the final design.
#
#       ┌ Design ┐
#           ↓
#       ┌ Filter 1 ┐  ↻ / ⧉ badges: what a schedule or the variants change
#           ↓
#       ┌ Physics ┐
#        ↓       ↓
#   ┌ Objective ┐ ┌ Constraint ┐
#        ↓       ↓
#       ┌ Updater ┐ ──→ back to Design
#
# Clicking a box opens its help window: what the part is and where it comes from.

import html

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

#: Box colour per kind of part.
KIND_COLOURS = {
    "design": "#4e79a7", "filter": "#59a14f", "material": "#b07aa1", "physics": "#f28e2b",
    "method": "#f28e2b", "objective": "#e15759", "constraint": "#ff9da7", "budget": "#ff9da7",
    "updater": "#76b7b2", "postprocessor": "#9c755f",
}

_MARGIN, _GUTTER, _GAP, _SPACING = 8, 24, 22, 8
_NODE_H, _BADGE_H, _AFTER_HEADING = 42, 15, 24


class PipelineGraph(QWidget):
    """The pipeline drawn as boxes and arrows; clicking a box opens its help."""

    node_clicked = Signal(object)   # the GraphNode clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._loop, self._after = [], []
        self._boxes = []          # (QRectF, GraphNode), in drawing order
        self._hover = None
        self.node_clicked.connect(self._open_help)

    # ── Content ───────────────────────────────────────────────────────────────

    def show_graph(self, loop, after):
        """Draw `loop` (rows of GraphNodes, the last feeding back to the first) and `after` (a chain)."""
        self._loop, self._after = [list(row) for row in loop], list(after)
        self._hover = None
        self.setMinimumHeight(int(self._height()))
        self.updateGeometry()
        self.update()

    def nodes(self):
        """Every node drawn, top to bottom."""
        return [n for row in self._loop for n in row] + list(self._after)

    @staticmethod
    def _row_height(row):
        return _NODE_H + _BADGE_H * max((len(n.badges) for n in row), default=0)

    def _height(self):
        loop = sum(self._row_height(r) + _GAP for r in self._loop)          # the last gap holds the loop arrow
        after = sum(self._row_height([n]) + _GAP for n in self._after)
        return _MARGIN + loop + (_AFTER_HEADING + after if self._after else 0)

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(240, int(self._height()))

    # ── Layout ────────────────────────────────────────────────────────────────

    def _layout(self):
        """[(rect, node)] and the row rectangles, for the current width."""
        left, right = _MARGIN + _GUTTER, self.width() - _MARGIN
        y, boxes, loop_rows = _MARGIN, [], []
        for row in self._loop:
            h = self._row_height(row)
            width = (right - left - _SPACING * (len(row) - 1)) / len(row)
            rects = [QRectF(left + i * (width + _SPACING), y, width, h) for i in range(len(row))]
            boxes += list(zip(rects, row, strict=True))
            loop_rows.append(rects)
            y += h + _GAP
        after_rows = []
        y += _AFTER_HEADING
        for node in self._after:
            h = self._row_height([node])
            rect = QRectF(left, y, right - left, h)
            boxes.append((rect, node))
            after_rows.append([rect])
            y += h + _GAP
        return boxes, loop_rows, after_rows

    # ── Drawing ───────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        boxes, loop_rows, after_rows = self._layout()
        self._boxes = boxes
        line = self.palette().text().color()
        line.setAlpha(150)
        painter.setPen(QPen(line, 1.3))
        painter.setBrush(line)
        for upper, lower in zip(loop_rows, loop_rows[1:], strict=False):
            self._connect(painter, upper, lower)
        if loop_rows:
            self._loop_arrow(painter, loop_rows[0], loop_rows[-1], line)
        if after_rows:
            first = after_rows[0][0]
            painter.setPen(self.palette().placeholderText().color())
            painter.drawText(QRectF(first.left(), first.top() - 18, first.width(), 16),
                             Qt.AlignLeft | Qt.AlignVCenter, "After the run, on the final design:")
            painter.setPen(QPen(line, 1.3))
            for upper, lower in zip(after_rows, after_rows[1:], strict=False):
                self._connect(painter, upper, lower)
        for rect, node in boxes:
            self._box(painter, rect, node)
        painter.end()

    def _box(self, painter, rect, node):
        colour = QColor(KIND_COLOURS.get(node.kind, "#888888"))
        from PySide6.QtWidgets import QApplication
        monochrome = QApplication.instance().property("appearance") == "sleek"
        if monochrome:
            colour = QColor("#ffffff")
        fill = QColor(colour)
        fill.setAlpha(25 if monochrome else 110 if node is self._hover else 55)
        painter.setPen(QPen(colour, 2 if node is self._hover else 1.2))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 6, 6)

        text = self.palette().text().color()
        inner = rect.adjusted(7, 3, -7, -3)
        small = QFont(self.font())
        small.setPointSizeF(max(self.font().pointSizeF() - 1.5, 6.5))
        painter.setFont(small)
        painter.setPen(colour.lighter(130) if self.palette().window().color().lightness() < 128 else colour.darker(130))
        painter.drawText(QRectF(inner.left(), inner.top(), inner.width(), 15), Qt.AlignLeft | Qt.AlignVCenter,
                         node.title)
        # The label in the normal font, or the small one when it would not fit (boxes sharing a row).
        fits = self.fontMetrics().horizontalAdvance(node.label) <= inner.width()
        painter.setFont(self.font() if fits else small)
        painter.setPen(text)
        label = painter.fontMetrics().elidedText(node.label, Qt.ElideRight, int(inner.width()))
        painter.drawText(QRectF(inner.left(), inner.top() + 15, inner.width(), 20), Qt.AlignLeft | Qt.AlignVCenter,
                         label)
        painter.setFont(small)
        for i, badge in enumerate(node.badges):
            top = inner.top() + 36 + i * _BADGE_H
            shown = painter.fontMetrics().elidedText(badge, Qt.ElideRight, int(inner.width()))
            painter.drawText(QRectF(inner.left(), top, inner.width(), _BADGE_H), Qt.AlignLeft | Qt.AlignVCenter,
                             shown)
        painter.setFont(self.font())

    def _connect(self, painter, upper, lower):
        """Arrows from every box of one row into every box of the next, through a shared bus."""
        mid = (upper[0].bottom() + lower[0].top()) / 2
        xs = [r.center().x() for r in upper + lower]
        for r in upper:
            painter.drawLine(QPointF(r.center().x(), r.bottom()), QPointF(r.center().x(), mid))
        if len(upper) > 1 or len(lower) > 1:
            painter.drawLine(QPointF(min(xs), mid), QPointF(max(xs), mid))
        for r in lower:
            painter.drawLine(QPointF(r.center().x(), mid), QPointF(r.center().x(), r.top() - 1))
            _arrowhead(painter, QPointF(r.center().x(), r.top() - 1), down=True)

    def _loop_arrow(self, painter, first, last, colour):
        """From the last row back up the left side into the first: the next iteration."""
        x = _MARGIN + _GUTTER / 2
        bottom = last[0].bottom() + 8
        start = last[0].center().x() if len(last) == 1 else min(r.center().x() for r in last)
        path = QPainterPath(QPointF(start, last[0].bottom()))
        path.lineTo(start, bottom)
        path.lineTo(x, bottom)
        target_y = first[0].center().y()
        path.lineTo(x, target_y)
        path.lineTo(first[0].left() - 1, target_y)
        pen = QPen(colour, 1.3, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.setPen(QPen(colour, 1.3))
        painter.setBrush(colour)
        _arrowhead(painter, QPointF(first[0].left() - 1, target_y), down=False)
        painter.setPen(self.palette().placeholderText().color())
        painter.drawText(QRectF(x + 4, bottom - 1, 200, 14), Qt.AlignLeft | Qt.AlignTop, "↺ next iteration")
        painter.setPen(QPen(colour, 1.3))

    # ── Interaction ───────────────────────────────────────────────────────────

    def _node_at(self, point):
        return next((node for rect, node in self._boxes if rect.contains(point)), None)

    def mouseMoveEvent(self, event):
        node = self._node_at(event.position())
        if node is not self._hover:
            self._hover = node
            self.setCursor(Qt.PointingHandCursor if node else Qt.ArrowCursor)
            self.update()
        if node is not None:
            extra = "".join(f"<br>{html.escape(b)}" for b in node.badges)
            QToolTip.showText(event.globalPosition().toPoint(),
                              f"<b>{html.escape(node.title)}</b>: {html.escape(node.label)}{extra}"
                              "<br><i>Click: what it is and where it comes from</i>", self)

    def leaveEvent(self, _event):
        self._hover = None
        self.update()

    def mousePressEvent(self, event):
        node = self._node_at(event.position())
        if node is not None and event.button() == Qt.LeftButton:
            self.node_clicked.emit(node)

    def _open_help(self, node):
        from ..help import HelpWindow
        HelpWindow.instance(self.window()).show_topic(node_topic(node))


def node_topic(node):
    """The help topic of one box of the network."""
    from ..help import plugin_topic, text_topic

    if node.cls is not None:
        topic = plugin_topic(node.cls, node.title.lower())
    elif node.kind == "budget":
        topic = text_topic(
            "Volume budget",
            "The design may use at most this fraction of the domain's material (Vol fraction, in step 1). "
            "Every method enforces it.",
            "The volume constraint of Sigmund's 99-line code (2001) and top88 (Andreassen et al. 2011).")
    else:
        topic = text_topic(node.title, f"{node.label}: the method's own design variables.",
                           "Set by the method chosen in step 2.")
    for badge in node.badges:
        topic.add("Changed during the run" if badge.startswith("↻") else "Evaluated in versions", badge)
    return topic


def _arrowhead(painter, tip, down):
    size = 5.0
    if down:
        points = [tip, QPointF(tip.x() - size, tip.y() - size * 1.4), QPointF(tip.x() + size, tip.y() - size * 1.4)]
    else:
        points = [tip, QPointF(tip.x() - size * 1.4, tip.y() - size), QPointF(tip.x() - size * 1.4, tip.y() + size)]
    painter.drawPolygon(QPolygonF(points))


class PipelineView(QGroupBox):
    """The selected pipeline as a network, and why any part of it is unavailable.

    It shows what the run will actually do (which filters, which physics,
    which responses, which updater), so swapping one part is visible at once,
    and a hidden panel (no filters, no constraints) is explained, not just gone.
    Under it, folded away, the stages as text, with what the network leaves
    out: what the optimiser sees, and which package each part comes from.
    """

    def __init__(self, parent=None):
        super().__init__("Pipeline", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self.graph = PipelineGraph()
        self._stages = QLabel()
        self._stages.setWordWrap(True)
        self._stages.setTextFormat(Qt.RichText)
        self._notes = QLabel()
        self._notes.setWordWrap(True)
        self._notes.setTextFormat(Qt.RichText)
        from .common import CollapsibleSection

        self.details = CollapsibleSection("Details as text", expanded=False)
        self.details.body_layout.addWidget(self._stages)
        layout.addWidget(self.graph)
        layout.addWidget(self._notes)
        layout.addWidget(self.details)
        self._plain_stages, self._plain_notes = [], []

    def show_pipeline(self, stages, notes, graph=None):
        """Show the network `graph` = (loop, after) when given, else [(stage, text), ...] as text; then the notes."""
        self._plain_stages, self._plain_notes = list(stages), list(notes)
        if graph is not None:
            self.graph.show_graph(*graph)
        self.graph.setVisible(graph is not None)
        rows = [f"<b>{html.escape(stage)}</b>: {html.escape(text)}" for stage, text in stages]
        self._stages.setText("<br>&nbsp;&nbsp;↓ ".join(rows) + "<br>&nbsp;&nbsp;↺ <i>next design</i>")
        self._stages.setVisible(bool(stages))
        self._notes.setVisible(bool(notes))
        self._notes.setText("<br>".join(f"<span style='color:gray'>• {html.escape(n)}</span>" for n in notes))

    def stages(self):
        """The [(stage, text), ...] of the current selection."""
        return list(self._plain_stages)

    def notes(self):
        """The displayed notes."""
        return list(self._plain_notes)
