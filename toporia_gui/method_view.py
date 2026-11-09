# toporia_gui/method_view.py — an interactive view of the supported solver pipeline.
# Moving boxes changes presentation only. The Run remains the execution contract;
# filter ordering is edited explicitly inside the filter chain, never by wiring.

import math

from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPalette, QPen
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
        self.add_button = QPushButton("+  Add function…")
        self.add_button.setMinimumHeight(36)
        self.add_button.setToolTip("Every function that can be added, and where it goes.")
        self.add_button.clicked.connect(lambda: self.open_add_dialog())
        bar.addWidget(self.add_button)
        for title, callback in (("↑ Parent", self.up), ("Whole tree", self.root),
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
        # The computation notes are not shown as a bar: the "?" help carries them, and Run explains
        # in a pop-up why a selection cannot run.
        self.notes = QLabel()
        self.notes.setWordWrap(True)
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
        #: The window's stage_graph(stage_id) -> pipeline graph of that optimisation, or None.
        self.stage_graph = None
        #: The window's mode_text() -> the kind of run, for the tree's run-mode block.
        self.mode_text = None
        #: Collapsed parts of the whole tree: optimisation ids, and "<id>/filters", "<id>/physics".
        self.collapsed = set()

    def set_workflow(self, tree, active_stage):
        self.tree, self.active_stage = tree, active_stage

    def _node(self, kind, title, label, function_id=None):
        from toporia_core.engine.pipeline import GraphNode
        node = GraphNode(kind, title, label)
        node.function_id = function_id
        return node

    def root(self):
        self.enter("root")

    def up(self):
        if "/" in self.context:
            self.enter(self.context.split("/")[0])
            return
        from toporia_core.framework.problem.workflow import nodes
        parent = next((node for node in nodes(self.tree) if any(c["id"] == self.context for c in node.get("children", []))), None) if self.tree else None
        self.enter(parent["id"] if parent else "root")

    def enter(self, context):
        self.context = context
        self.context_changed.emit(context)
        self._signature = None
        self.show_pipeline(self._graph, self._notes)

    def _activate(self, node):
        toggle = getattr(node, "toggle", None)
        if toggle:
            QTimer.singleShot(0, lambda: self._toggle(toggle, getattr(node, "stage", None)))
            return
        target = getattr(node, "function_id", None)
        if target:
            QTimer.singleShot(0, lambda: self._enter_function(target))
            return
        stage = getattr(node, "stage", None)
        if stage and stage != self.active_stage:
            self.stage_requested.emit(stage)
        self.selected.emit(node)

    def _toggle(self, key, stage=None):
        """Collapse or show one optimisation, filter chain or physics calculation of the tree."""
        if stage and stage != self.active_stage:
            self.stage_requested.emit(stage)
        self.collapsed ^= {key}
        self._signature = None
        self.show_pipeline(self._graph, self._notes)

    def _enter_function(self, target):
        from toporia_core.framework.problem.workflow import nodes
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
        from toporia_core.framework.problem.workflow import nodes
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
            from .workflow_ui import FIXED
            for label, kind, name, reason in (self.offers(where) if self.offers else ()):
                item = offer(label, kind, name)
                if not reason:
                    continue
                if reason.startswith(FIXED):      # nothing in this step can make it fit
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    if reason.startswith("not installed"):
                        item.setText(f"{label}  (not installed)")
                    else:                         # "it works in 3-D; this problem is 2-D ..."
                        item.setText(f"{label}  ({reason.split(';')[0].removeprefix('it works in ')} only)")
                    item.setToolTip(f"{label}\nUnavailable here: {reason}")
                else:                             # selectable; choosing it changes what conflicts with it
                    item.setForeground(self.palette().brush(QPalette.Disabled, QPalette.Text))
                    item.setData(Qt.UserRole + 1, reason)
                    item.setToolTip(f"{label}\nDoes not fit the current selection: {reason}.\n"
                                    "Choosing it changes the parts that conflict with it.")

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
            from toporia_core.engine.pipeline import part_dims
            from toporia_library.filters import FILTERS
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
        if self.context == "root" and self.tree is not None and self.stage_graph is not None:
            self.notes.setText("\n".join(notes))
            self._show_tree()
            return
        loop, after = self._local_graph(graph)
        self.library_widget.setVisible(False)          # offered through "+ Add function…"
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

    # ── The whole tree ───────────────────────────────────────────────────────

    W, H = 280, 118     # column and row pitch of the tree layout

    def _tree_layout(self):
        """Place every block of the whole tree: [(node, x, y)] and edges [(i, j, back)].

        Always shown: the operating space, the kind of run, the optimisations and how they
        relate (in sequence with a transformation between, or in parallel with their
        combination), and the export.  Each optimisation, and in it the filter chain and
        the physics calculation, can be collapsed.
        """
        placed, edges = [], []
        W, H = self.W, self.H

        def put(node, x, y):
            placed.append((node, x, y))
            return len(placed) - 1

        def link(sources, targets, back=False):
            edges.extend((a, b, back) for a in sources for b in targets)

        def stage_rows(stage):
            sid = stage["id"]
            graph = self.stage_graph(sid)
            if graph is None:
                return [[self._node("note", "Cannot describe", "This optimisation's settings are invalid")]]
            loop, _ = graph
            physics_kinds = {"material", "physics", "objective", "constraint", "budget"}
            rows, filters, physics = [], [], []
            for row in loop:                      # design, filters…, material, physics, responses, updater
                kinds = {n.kind for n in row}
                if kinds == {"filter"}:
                    if not filters:
                        rows.append(["filters"])
                    filters.append(row)
                elif kinds & physics_kinds:
                    if not physics:
                        rows.append(["physics"])
                    physics.append(row)
                else:
                    rows.append(row)
            out = []
            for row in rows:
                if row == ["filters"]:
                    key = f"{sid}/filters"
                    closed = key in self.collapsed
                    group = self._node("group", "Filter chain", f"{len(filters)} filter{'s' * (len(filters) != 1)}"
                                       + (" · ▸ show" if closed else " · ▾ hide"))
                    group.toggle, group.stage = key, sid
                    out.append([group])
                    if not closed:
                        out += filters
                elif row == ["physics"]:
                    key = f"{sid}/physics"
                    closed = key in self.collapsed
                    group = self._node("group", "Physics calculation", "Material · physics · responses"
                                       + (" · ▸ show" if closed else " · ▾ hide"))
                    group.toggle, group.stage = key, sid
                    out.append([group])
                    if not closed:
                        out += physics
                else:
                    out.append(row)
            convergence = self._node("convergence", "Convergence", "Iteration limit and tolerance")
            out.append([convergence])
            for row in out:
                for node in row:
                    if not hasattr(node, "stage"):
                        node.stage = sid
            return out

        def layout(item, x, y):
            """Place `item` with its top-left at (x, y): (entries, exits, width, height)."""
            kind = item["kind"]
            if kind == "optimization":
                sid = item["id"]
                closed = sid in self.collapsed
                header = self._node("optimization", item["name"],
                                    ("▸ collapsed · select to show its loop" if closed
                                     else "▾ its loop to the right · select to collapse"))
                header.toggle, header.stage = sid, sid
                head = put(header, x, y)
                if closed:
                    return [head], [head], W, H
                previous, first, left, height = [head], None, x + W, H
                for row in stage_rows(item):                  # left to right; a row's parts stacked
                    indices = [put(node, left, y + i * H) for i, node in enumerate(row)]
                    link(previous, indices)
                    if first is None:
                        first = indices
                    previous, left, height = indices, left + W, max(height, len(row) * H)
                link(previous, first or [head], back=True)        # the optimisation loop
                return [head], [head], left - x, height + 30      # its result leaves from the header
            children = item.get("children", [])
            if kind == "sequential":
                entries, exits, top, width = None, None, y, W
                for i, child in enumerate(children):
                    if i:
                        step = put(self._node("transform", "Transformation",
                                              "Previous density ≥ 0.5 → allowed domain"), x, top)
                        link(exits, [step])
                        exits, top = [step], top + H
                    e, o, w, h = layout(child, x, top)
                    if entries is None:
                        entries = e
                    else:
                        link(exits, e)
                    exits, top, width = o, top + h, max(width, w)
                return entries or [], exits or [], width, top - y
            # parallel: the branches one under another, each fed the same domain, then combined
            entries, exits, top, width = [], [], y, W
            for child in children:
                e, o, w, h = layout(child, x + 40, top)
                entries += e
                exits += o
                top, width = top + h, max(width, w + 40)
            combine = put(self._node("combine", "Boolean combination", item.get("operation", "union")), x, top)
            link(exits, [combine])
            return entries, [combine], width, top + H - y

        domain = put(self._node("domain", "Operating space", "Physical domain, supports, loads and mesh"), 0, 0)
        mode = self._node("mode", "Run mode", (self.mode_text() if self.mode_text else "Run One")
                          + " · step 3")
        run = put(mode, 0, H)
        link([domain], [run])
        entries, exits, _, height = layout(self.tree, 0, 2 * H)
        link([run], entries)
        export = put(self._node("export", "Export", "Terminal file output · step 5"), 0, 2 * H + height)
        link(exits, [export])
        return placed, edges

    def _show_tree(self):
        """Draw the whole tree; rebuilt only when what it shows changes, so arranging survives."""
        self.library.clear()
        self.library_widget.setVisible(False)
        self.breadcrumb.setText("Whole tree")
        self.input_contract.setText("Select an optimisation, the filter chain or the physics calculation to "
                                    "collapse or show it; select any other block to edit it.")
        self.output_contract.setText("")
        placed, edges = self._tree_layout()
        signature = "tree" + repr([(n.kind, n.title, n.label, tuple(n.badges), x, y) for n, x, y in placed]) + repr(edges)
        if signature == self._signature:
            return
        self._building = True
        self._signature = signature
        self.blocks, self.edges, self.filter_frame = {}, [], None
        scene = self.view.scene()
        scene.clear()
        made = []
        for index, (node, x, y) in enumerate(placed):
            key = f"tree:{getattr(node, 'stage', '')}:{node.kind}:{node.title}:{index}"
            block = _Block(node, key, self._moved, self._activate)
            scene.addItem(block)
            block.setPos(x, y)
            self.blocks[key] = block
            made.append(block)
        for a, b, back in edges:
            edge = QGraphicsPathItem()
            edge.setPen(QPen(QColor("#9baabd"), 2, Qt.DashLine if back else Qt.SolidLine))
            edge.setZValue(-1)
            scene.addItem(edge)
            self.edges.append((made[a], made[b], edge, back))
        self._building = False
        self._moved()
        self.fit()
        self.refresh_appearance()

    def open_add_dialog(self):
        """Every function that can be added, and, where there is a choice, where it goes."""
        from .add_function import AddFunctionDialog
        dialog = AddFunctionDialog(self._add_entries(), self.active_stage, self)
        if dialog.exec() and dialog.choice is not None:
            kind, name, place = dialog.choice
            self._add_at(kind, name, place)

    def _add_entries(self):
        """(label, kind, name, reason, places) for the dialog; places are (label, (where, id))."""
        from toporia_core.framework.problem.workflow import nodes
        if self.tree is None:
            return []
        stages = [n for n in nodes(self.tree) if n["kind"] == "optimization"]
        containers = [n for n in nodes(self.tree) if n["kind"] in {"sequential", "parallel"}]
        here = [(s["name"], ("stage", s["id"])) for s in stages]
        entries = []
        for where in ("loop", "physics"):
            for label, kind, name, reason in (self.offers(where) if self.offers else ()):
                entries.append((label, kind, name, reason, here))
        from toporia_core.engine.pipeline import part_dims
        from toporia_library.filters import FILTERS
        dims = getattr(self, "dimensions", 2)
        entries += [(f"+ Filter: {cls.label}", "filter", cls.name, "", here) for cls in FILTERS.classes()
                    if dims in (part_dims("filter", cls) or (dims,))]
        entries += [("Parameter schedules", "inspect", "schedule", "", here),
                    ("Design variants", "inspect", "variants", "", here)]
        whole = [("After the whole workflow", ("root", None))]
        entries += [("+ Sequential stage: another optimisation after this one", "composition", "sequential", "", whole),
                    ("+ Parallel branch: another optimisation beside this one", "composition", "parallel", "", whole)]
        if containers:
            inside = [(c["name"], ("container", c["id"])) for c in containers]
            entries.append(("+ Optimisation inside a sequence or parallel group", "composition", "optimization", "", inside))
        return entries

    def _add_at(self, kind, name, place):
        where, target = place
        if where == "stage" and target != self.active_stage:
            self.stage_requested.emit(target)
        previous = self.context
        if where == "container":
            self.context = target
        elif where == "root":
            self.context = "root"
        self.add_requested.emit(kind, name)
        self.context = previous
        self._signature = None
        self.show_pipeline(self._graph, self._notes)

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
            ra, rb = a.sceneBoundingRect(), b.sceneBoundingRect()
            if back and rb.right() < ra.left():
                # A loop running left to right closes underneath its row.
                start = QPointF(ra.center().x(), ra.bottom())
                end = QPointF(rb.center().x(), rb.bottom())
                below = max(ra.bottom(), rb.bottom()) + 18
                path = QPainterPath(start)
                path.lineTo(start.x(), below)
                path.lineTo(end.x(), below)
                path.lineTo(end)
                unit, normal = QPointF(0, -1), QPointF(1, 0)
                path.lineTo(end - unit * 10 + normal * 5)
                path.moveTo(end)
                path.lineTo(end - unit * 10 - normal * 5)
                edge.setPath(path)
                continue
            if not back and rb.left() >= ra.right() - 1:
                # Side by side: from the right edge into the left edge.
                start = QPointF(ra.right(), ra.center().y())
                end = QPointF(rb.left(), rb.center().y())
                path = QPainterPath(start)
                path.cubicTo(start + QPointF(30, 0), end - QPointF(30, 0), end)
                unit, normal = QPointF(1, 0), QPointF(0, 1)
                path.lineTo(end - unit * 10 + normal * 5)
                path.moveTo(end)
                path.lineTo(end - unit * 10 - normal * 5)
                edge.setPath(path)
                if hasattr(edge, "label"):
                    edge.label.setPos((start + end) / 2 + QPointF(-20, -24))
                continue
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
