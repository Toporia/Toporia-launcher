# apps/gui/method_view.py — an interactive view of the supported solver pipeline.
# Moving boxes changes presentation only. The Run remains the execution contract;
# filter ordering is edited explicitly inside the filter chain, never by wiring.

import math

from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .panels.pipeline import KIND_COLOURS


class _Block(QGraphicsRectItem):
    """A selectable pipeline block; its position has no effect on computation."""

    def __init__(self, node, key, moved, activated=None):
        super().__init__(0, 0, 250, 76 + 16 * len(node.badges))
        self.node, self.key, self.moved = node, key, moved
        self.activated = activated
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
        # PySide needs Python references here; otherwise the wrappers delete
        # these child items even though the rectangle is their graphics parent.
        self.text_items = (title, label)
        self.refresh_appearance()
        self.setToolTip("Select to edit parameters. Drag to arrange. Connections remain fixed.")

    def refresh_appearance(self):
        from .appearance import colours
        colors = colours(QApplication.instance())
        self.setBrush(QBrush(colors["surface"]))
        self.setPen(QPen(colors["border"], 1))
        self.text_items[0].setDefaultTextColor(colors["text"])
        self.text_items[1].setDefaultTextColor(colors["text"])

    def mouseDoubleClickEvent(self, event):
        if self.activated:
            self.activated(self.node)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self._press = QPointF(event.scenePos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.activated and (event.scenePos() - self._press).manhattanLength() < 4:
            self.activated(self.node)

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
        from .appearance import colours
        self.setBackgroundBrush(colours(self)["background"])

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
    stage_requested = Signal(str)
    add_requested = Signal(str, str)
    context_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.breadcrumb = QLabel("Workflow")
        bar.addWidget(self.breadcrumb)
        bar.addStretch()
        for title, callback in (("↑ Parent", self.up), ("Workflow", self.root),
                                ("Fit", self.fit), ("Reset layout", self.reset_layout)):
            button = QPushButton(title)
            button.setMinimumHeight(36)
            button.clicked.connect(callback)
            bar.addWidget(button)
        layout.addLayout(bar)
        from .help import HelpButton, text_topic
        bar.addWidget(HelpButton(lambda: text_topic(
            self.breadcrumb.text(), self.input_contract.text() + "\n" + self.output_contract.text()
            + "\nSelect a container to enter its local network; select a computational leaf to edit its parameters. Dragging changes presentation only. Library insertion changes the saved execution contract.").add("Computation notes", self.notes.text())))
        self.input_contract = QLabel()
        self.input_contract.setWordWrap(True)
        layout.addWidget(self.input_contract)
        body = QHBoxLayout()
        self.library = QListWidget()
        self.library.setMaximumWidth(260)
        self.library.setMinimumWidth(170)
        self.library.setToolTip("Double-click a compatible function to insert it in this local network.")
        self.library.itemActivated.connect(self._add)
        self.library_widget = QWidget()
        library_box = QVBoxLayout(self.library_widget)
        library_box.setContentsMargins(0, 0, 0, 0)
        library_box.addWidget(QLabel("Function library"))
        library_box.addWidget(self.library, 1)
        insert = QPushButton("+ Insert selected")
        insert.setMinimumHeight(38)
        insert.clicked.connect(lambda: self._add(self.library.currentItem()))
        library_box.addWidget(insert)
        body.addWidget(self.library_widget)
        self.view = DiagramView()
        body.addWidget(self.view, 1)
        layout.addLayout(body, 1)
        self.output_contract = QLabel()
        self.output_contract.setWordWrap(True)
        layout.addWidget(self.output_contract)
        self.notes = QLabel()
        self.notes.setWordWrap(True)
        from .panels.common import CollapsibleSection
        note_section = CollapsibleSection("Computation notes", expanded=False)
        note_section.body_layout.addWidget(self.notes)
        layout.addWidget(note_section)
        self.blocks, self.edges, self.positions = {}, [], {}
        self.filter_frame = None
        self._building = False
        self._signature = None
        self.context = "root"
        self.tree = None
        self.active_stage = None
        self._graph = ([], [])
        self._notes = []
        #: The window's offers(where) -> [(label, kind, name, reason)]; a reason greys the entry out.
        self.offers = None

    def set_workflow(self, tree, active_stage):
        self.tree, self.active_stage = tree, active_stage

    def _node(self, kind, title, label, function_id=None):
        from toporia.engine.pipeline import GraphNode
        node = GraphNode(kind, title, label)
        node.function_id = function_id
        return node

    def root(self):
        self.enter("root")

    def up(self):
        if "/" in self.context:
            self.enter(self.context.split("/")[0])
            return
        from toporia.framework.problem.workflow import nodes
        parent = next((node for node in nodes(self.tree) if any(c["id"] == self.context for c in node.get("children", []))), None) if self.tree else None
        self.enter(parent["id"] if parent else "root")

    def enter(self, context):
        self.context = context
        self.context_changed.emit(context)
        self._signature = None
        self.show_pipeline(self._graph, self._notes)

    def _activate(self, node):
        target = getattr(node, "function_id", None)
        if target:
            QTimer.singleShot(0, lambda: self._enter_function(target))
        else:
            self.selected.emit(node)

    def _enter_function(self, target):
        from toporia.framework.problem.workflow import nodes
        stage = next((node for node in nodes(self.tree) if node["id"] == target), None) if self.tree else None
        if stage and stage["kind"] == "optimization":
            self.stage_requested.emit(target)
        self.enter(target)

    def _add(self, item):
        if item is None:
            return
        value = item.data(Qt.UserRole)
        if value:
            self.add_requested.emit(*value)

    def _local_graph(self, graph):
        from toporia.framework.problem.workflow import nodes
        self.library.clear()

        def offer(label, kind, name):
            from .appearance import themed_icon
            original = self.style().standardIcon(QStyle.SP_FileIcon)
            item = QListWidgetItem(themed_icon(original), label, self.library)
            item._basic_icon = original
            item.setData(Qt.UserRole, (kind, name))
            item.setToolTip(label)
            item.setSizeHint(QSize(150, 36))
            return item

        def offer_parts(where):
            """Every registered part for this place; the incompatible ones greyed out, saying why."""
            for label, kind, name, reason in (self.offers(where) if self.offers else ()):
                item = offer(label, kind, name)
                if reason:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setToolTip(f"{label}\nUnavailable here: {reason}")

        if self.tree is None:
            return graph
        functions = {node["id"]: node for node in nodes(self.tree)}
        context, _, sub = self.context.partition("/")
        if context != "root" and context not in functions:
            self.context, context, sub = "root", "root", ""
        domain = self._node("domain", "Operating space", "Physical domain, supports, loads and mesh")
        export = self._node("export", "Export", "Terminal file output · step 5")

        def function(node):
            return self._node(node["kind"], node["name"], "Open local network", node["id"])

        if context == "root":
            self.breadcrumb.setText("Workflow")
            self.input_contract.setText("Input · shared operating-space definition")
            self.output_contract.setText("Output · finished design → terminal export function")
            offer("+ Sequential stage", "composition", "sequential")
            offer("+ Parallel branch", "composition", "parallel")
            return [[domain], [function(self.tree)], [export]], []
        node = functions[context]
        self.breadcrumb.setText("Workflow › " + node["name"] + (" › " + sub.capitalize() if sub else ""))
        if node["kind"] in {"sequential", "parallel"}:
            offer("+ Optimization", "composition", "optimization")
            offer("+ Sequential sub-function", "composition", "sequential")
            offer("+ Parallel sub-function", "composition", "parallel")
            if node["kind"] == "parallel":
                for operation in ("union", "intersection", "difference"):
                    offer("Combine: " + operation, "operation", operation)
                operation = node.get("operation", "union")
                self.input_contract.setText("Input · same domain to each independent branch")
                self.output_contract.setText(f"Output · {operation} of completed branches (difference: first minus all others)")
                combined = self._node("combine", "Boolean combination", operation)
                return [[domain], [function(child) for child in node["children"]], [combined]], []
            self.input_contract.setText("Input · operating domain or preceding volume")
            self.output_contract.setText("Output · final stage's optimized density")
            rows = []
            for i, child in enumerate(node["children"]):
                if i:
                    rows.append([self._node("transform", "Transformation", "Previous density ≥ 0.5 → allowed domain\nBudget relative to allowed volume")])
                rows.append([function(child)])
            return rows, []
        loop, _ = graph
        flat = [n for row in loop for n in row]
        self.input_contract.setText("Input · design variables and allowed domain")
        self.output_contract.setText("Output · updated density, objective and iteration statistics")
        if any(n.kind == "method" for n in flat):
            offer_parts("loop")
            return loop, []
        if sub == "filters":
            from toporia.engine.pipeline import part_dims
            from toporia.plugins.filters import FILTERS
            dims = getattr(self, "dimensions", 2)
            if any(n.kind == "design" for n in flat):
                for cls in FILTERS.classes():
                    if dims in (part_dims("filter", cls) or (dims,)):
                        offer("+ " + cls.label, "filter", cls.name)
            self.input_contract.setText("Input · element densities")
            self.output_contract.setText("Output · filtered physical densities in list order")
            return [[n] for n in flat if n.kind == "filter"], []
        if sub == "physics":
            self.input_contract.setText("Input · physical density, material law and boundary conditions")
            self.output_contract.setText("Output · objective, constraints and sensitivities")
            offer_parts("physics")
            return [[n for n in row if n.kind in {"physics", "material", "objective", "constraint", "budget"}] for row in loop
                    if any(n.kind in {"physics", "material", "objective", "constraint", "budget"} for n in row)], []
        offer("+ Filter (open filter chain)", "navigate", context + "/filters")
        rows = [[n] for n in flat if n.kind == "design"]
        rows.append([self._node("filters", "Filter chain", "Open / insert filters", context + "/filters")])
        rows.append([self._node("calculation", "Physics calculation", "Material · physics · responses", context + "/physics")])
        rows += [[n] for n in flat if n.kind in {"method", "updater"}]
        rows.append([self._node("convergence", "Convergence", "Iteration limit and tolerance")])
        offer("Parameter schedules", "inspect", "schedule")
        offer("Design variants", "inspect", "variants")
        offer_parts("loop")
        return rows, []

    def show_pipeline(self, graph, notes):
        """Rebuild only when semantic content changes; preserve user positions."""
        self._graph, self._notes = graph, notes
        loop, after = self._local_graph(graph)
        self.library_widget.setVisible(self.library.count() > 0)
        loop = [row for row in loop if row]
        signature = self.context + repr([(n.kind, n.title, n.label, n.badges) for row in loop for n in row]) + repr(after)
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
                identity = getattr(node, "function_id", None) or node.title
                key = f"{self.context}:{node.kind}:{identity}:{col}"
                block = _Block(node, key, self._moved, self._activate)
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
                    if self.tree is not None:
                        text = "same input domain" if a.node.kind == "domain" else "after branch completion" if b.node.kind == "combine" else "output → input"
                        label = QGraphicsTextItem(text, edge)
                        label.setFont(QFont("Segoe UI", 8))
                        label.setDefaultTextColor(QColor("#cbd5e1"))
                        edge.label = label
        if loop and self.context not in {"root"} and self.context.split("/")[0] == self.active_stage and "/" not in self.context:
            edge = QGraphicsPathItem()
            edge.setPen(QPen(QColor("#9baabd"), 2, Qt.DashLine))
            edge.setZValue(-1)
            scene.addItem(edge)
            self.edges.append((rows[len(loop) - 1][0], rows[0][0], edge, True))
        self._building = False
        self._moved()
        self.fit()
        self.refresh_appearance()

    def refresh_appearance(self):
        from .appearance import colours
        colors = colours(self)
        self.view.setBackgroundBrush(colors["background"])
        for block in self.blocks.values():
            block.refresh_appearance()
        for _, _, edge, _ in self.edges:
            pen = edge.pen()
            pen.setColor(colors["muted"])
            pen.setWidthF(1)
            edge.setPen(pen)
            if hasattr(edge, "label"):
                edge.label.setDefaultTextColor(colors["muted"])
        if self.filter_frame is not None:
            self.filter_frame.setPen(QPen(colors["border"], 1, Qt.DashLine))
            self.filter_frame.setBrush(Qt.NoBrush)
        self.view.viewport().update()

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
            if not back:
                path.cubicTo(start + QPointF(0, 40), end - QPointF(0, 40), end)
                tangent = QPointF(0, 40)  # exact terminal derivative of the cubic
            else:
                tangent = end - path.currentPosition()
                path.lineTo(end)
            length = math.hypot(tangent.x(), tangent.y()) or 1
            unit = tangent / length
            normal = QPointF(-unit.y(), unit.x())
            path.lineTo(end - unit * 10 + normal * 5)
            path.moveTo(end)
            path.lineTo(end - unit * 10 - normal * 5)
            edge.setPath(path)
            if hasattr(edge, "label"):
                edge.label.setPos((start + end) / 2 + QPointF(8, -28))
        self.positions.update({key: [block.x(), block.y()] for key, block in self.blocks.items()})
        if self.filter_frame is not None:
            filters = [block.sceneBoundingRect() for block in self.blocks.values() if block.node.kind == "filter"]
            bounds = filters[0]
            for rect in filters[1:]:
                bounds = bounds.united(rect)
            self.filter_frame.setRect(bounds.adjusted(-15, -15, 15, 15))
        self.arranged.emit(self.positions)

    def fit(self):
        """Fit all blocks and the feedback connection into the current viewport."""
        bounds = self.view.scene().itemsBoundingRect().adjusted(-35, -35, 35, 35)
        self.view.setSceneRect(bounds)
        self.view.fitInView(bounds, Qt.KeepAspectRatio)
        scale = self.view.transform().m11()
        if scale > 1.25:
            self.view.scale(1.25 / scale, 1.25 / scale)
            self.view.centerOn(bounds.center())

    def reset_layout(self):
        """Return to a readable default without changing the solver configuration."""
        self.positions = {}
        self._signature = None
        self.parent().window()._refresh_pipeline()
