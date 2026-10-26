# apps/gui/method_view.py — an interactive view of the supported solver pipeline.
# Moving boxes changes presentation only. The Run remains the execution contract;
# filter ordering is edited explicitly inside the filter chain, never by wiring.

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .panels.pipeline import KIND_COLOURS


class _Block(QGraphicsRectItem):
    """A selectable pipeline block; its position has no effect on computation."""

    def __init__(self, node, key, moved):
        super().__init__(0, 0, 250, 76 + 16 * len(node.badges))
        self.node, self.key, self.moved = node, key, moved
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        colour = QColor(KIND_COLOURS.get(node.kind, "#64748b"))
        self.setPen(QPen(colour, 2))
        self.setBrush(QBrush(QColor("#202b37")))
        title = QGraphicsTextItem(node.title, self)
        title.setDefaultTextColor(colour.lighter(160))
        title.setPos(10, 3)
        label = QGraphicsTextItem(node.label + "\n" + "\n".join(node.badges), self)
        label.setDefaultTextColor(QColor("#edf2f7"))
        label.setTextWidth(232)
        label.setPos(10, 25)
        for child in (title, label):
            child.setAcceptedMouseButtons(Qt.NoButton)
        self.setToolTip("Select to edit parameters. Drag to arrange. Connections remain fixed.")

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.moved()
        return super().itemChange(change, value)


class DiagramView(QGraphicsView):
    """Zoomable, pannable scene; middle-button or empty-space dragging pans."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#151d26"))

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        scale = self.transform().m11() * factor
        if 0.08 < scale < 8:
            self.scale(factor, factor)
        event.accept()


class MethodWorkspace(QWidget):
    """Graph navigation and selection on the main canvas of the Method step."""

    selected = Signal(object)
    arranged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Method · select a block to edit its settings"))
        bar.addStretch()
        for title, callback in (("Fit", self.fit), ("Reset layout", self.reset_layout)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            bar.addWidget(button)
        layout.addLayout(bar)
        self.view = DiagramView()
        layout.addWidget(self.view)
        self.notes = QLabel()
        self.notes.setWordWrap(True)
        layout.addWidget(self.notes)
        self.blocks, self.edges, self.positions = {}, [], {}
        self.filter_frame = None
        self._building = False
        self._signature = None
        self.view.scene().selectionChanged.connect(self._selection)

    def show_pipeline(self, graph, notes):
        """Rebuild only when semantic content changes; preserve user positions."""
        loop, after = graph
        signature = repr([(n.kind, n.title, n.label, n.badges) for row in loop for n in row]) + repr(after)
        self.notes.setText("\n".join(notes))
        if signature == self._signature:
            return
        self._building = True
        self._signature = signature
        self.blocks, self.edges = {}, []
        self.filter_frame = None
        scene = self.view.scene()
        scene.clear()
        rows = []
        for row_index, row in enumerate([*loop, *[[n] for n in after]]):
            blocks = []
            for col, node in enumerate(row):
                key = f"{node.kind}:{node.title}:{col}"
                block = _Block(node, key, self._moved)
                scene.addItem(block)
                pos = self.positions.get(key, [col * 280, row_index * 120])
                block.setPos(*pos)
                self.blocks[key] = block
                blocks.append(block)
            rows.append(blocks)
        if any(block.node.kind == "filter" for block in self.blocks.values()):
            self.filter_frame = QGraphicsRectItem()
            self.filter_frame.setPen(QPen(QColor("#547b58"), 1, Qt.DashLine))
            self.filter_frame.setBrush(QColor(60, 90, 60, 25))
            self.filter_frame.setZValue(-2)
            scene.addItem(self.filter_frame)
        for upper, lower in zip(rows, rows[1:], strict=False):
            for a in upper:
                for b in lower:
                    edge = QGraphicsPathItem()
                    edge.setPen(QPen(QColor("#9baabd"), 2))
                    edge.setZValue(-1)
                    scene.addItem(edge)
                    self.edges.append((a, b, edge, False))
        if loop:
            edge = QGraphicsPathItem()
            edge.setPen(QPen(QColor("#9baabd"), 2, Qt.DashLine))
            edge.setZValue(-1)
            scene.addItem(edge)
            self.edges.append((rows[len(loop) - 1][0], rows[0][0], edge, True))
        self._building = False
        self._moved()
        self.fit()

    def _moved(self):
        """Follow dragged blocks with their fixed connection paths."""
        if self._building:
            return
        from PySide6.QtGui import QPainterPath
        for a, b, edge, back in self.edges:
            start = a.pos() + QPointF(125, a.rect().height())
            end = b.pos() + QPointF(125, 0)
            path = QPainterPath(start)
            if back:
                left = min(a.x(), b.x()) - 65
                path.lineTo(start.x(), start.y() + 20)
                path.lineTo(left, start.y() + 20)
                path.lineTo(left, end.y() - 20)
                path.lineTo(end.x(), end.y() - 20)
            path.lineTo(end)
            path.lineTo(end + QPointF(-5, -8))
            path.moveTo(end)
            path.lineTo(end + QPointF(5, -8))
            edge.setPath(path)
        self.positions = {key: [block.x(), block.y()] for key, block in self.blocks.items()}
        if self.filter_frame is not None:
            filters = [block.sceneBoundingRect() for block in self.blocks.values() if block.node.kind == "filter"]
            bounds = filters[0]
            for rect in filters[1:]:
                bounds = bounds.united(rect)
            self.filter_frame.setRect(bounds.adjusted(-15, -15, 15, 15))
        self.arranged.emit(self.positions)

    def _selection(self):
        """Route the selected part to the generated parameter panel."""
        if not self._building:
            selected = [item for item in self.view.scene().selectedItems() if isinstance(item, _Block)]
            if selected:
                self.selected.emit(selected[0].node)

    def fit(self):
        """Fit all blocks and the feedback connection into the current viewport."""
        bounds = self.view.scene().itemsBoundingRect().adjusted(-35, -35, 35, 35)
        self.view.setSceneRect(bounds)
        self.view.fitInView(bounds, Qt.KeepAspectRatio)

    def reset_layout(self):
        """Return to a readable default without changing the solver configuration."""
        self.positions = {}
        self._signature = None
        self.parent().window()._refresh_pipeline()
