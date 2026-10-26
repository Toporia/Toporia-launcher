# apps/gui/editor.py — 2D problem workspace: tools, geometry scene, object list and inspector.
# All edits update physical definitions together; scene selection and list selection
# share object IDs. Undo stores definitions, never mesh indices or screenshots.

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .geometry import make_object, objects_from_scenario

COLOURS = {"support": "#49a5db", "load": "#f87777", "solid": "#c2cad3", "void": "#e1bc66", "domain": "#82cfa0"}


class GeometryItem(QGraphicsPathItem):
    """A rendered definition; dragging commits one undoable physical translation."""

    def __init__(self, obj, released, readonly):
        super().__init__()
        self.obj, self.released = obj, released
        path = QPainterPath()
        w, h, _ = obj["size"]
        shape = obj["shape"]
        if shape == "point":
            path.addEllipse(QPointF(), 0.8, 0.8)
        elif shape == "line":
            path.lineTo(w, -h)
        elif shape == "circle":
            path.addEllipse(-w / 2, -h / 2, w, h)
        elif shape == "polygon":
            path.addPolygon(QPolygonF([QPointF(x, -y) for x, y in obj["vertices"]]))
            path.closeSubpath()
        else:
            path.addRect(0, -h, w, h)
        self.setPath(path)
        colour = QColor(COLOURS[obj["role"]])
        self.setPen(QPen(colour, 0))
        fill = QColor(colour)
        fill.setAlpha(95 if obj["role"] in {"solid", "void", "domain"} else 45)
        self.setBrush(QBrush(fill))
        self.setPos(obj["position"][0], -obj["position"][1])
        self.setRotation(-obj["rotation"][2])
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable, not readonly)
        self.setToolTip(f"{obj['name']} · {obj['role']}")
        self.setZValue(2 if shape in {"point", "line"} else 1)

    def shape(self):
        """Give points and thin lines a useful hit target at any zoom level."""
        from PySide6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(1.5)
        return super().shape().united(stroker.createStroke(self.path()))

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        point = self.pos()
        if [point.x(), -point.y()] != self.obj["position"][:2]:
            self.released(self.obj["id"], point.x(), -point.y())


class ProblemView(QGraphicsView):
    """Physical XY view with selection, zoom, pan and click-based creation tools."""

    placed = Signal(float, float)
    cursor_position = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.tool = "select"
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#17212b"))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        if 0.05 < self.transform().m11() * factor < 500:
            self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        if self.tool not in {"select", "pan"} and event.button() == Qt.LeftButton:
            point = self.mapToScene(event.position().toPoint())
            self.placed.emit(point.x(), -point.y())
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        self.cursor_position.emit(point.x(), -point.y())
        super().mouseMoveEvent(event)


class ProblemEditor(QWidget):
    """Shared scene/list/inspector and undoable operations on one physical problem."""

    changed = Signal(object, object)  # Scenario, explicit object list

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenario = None
        self.objects = []
        self.readonly = True
        self._loading = False
        self._undo, self._redo, self._items = [], [], {}
        self._first = None
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.tool_buttons = []
        for tool in ("Select", "Pan", "Point", "Line", "Rectangle", "Circle"):
            button = QPushButton(tool)
            button.clicked.connect(lambda _=False, t=tool: self.set_tool(t.lower()))
            toolbar.addWidget(button)
            self.tool_buttons.append(button)
        toolbar.addStretch()
        for text, callback in (("Undo", self.undo), ("Redo", self.redo), ("Fit", self.fit)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
            setattr(self, text.lower() + "_button", button)
        layout.addLayout(toolbar)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        body = QSplitter()
        self.view = ProblemView()
        body.addWidget(self.view)
        inspector = QWidget()
        inspector.setMaximumWidth(300)
        controls = QVBoxLayout(inspector)
        self.object_list = QListWidget()
        self.object_list.setMaximumHeight(180)
        controls.addWidget(QLabel("Objects"))
        controls.addWidget(self.object_list)
        self.object_form = QWidget()
        form = QFormLayout(self.object_form)
        self.name = QLineEdit()
        form.addRow("Name", self.name)
        self.role = QComboBox()
        for role in COLOURS:
            self.role.addItem(role.title(), role)
        form.addRow("Role", self.role)
        self.fields = {}
        for label, key, value in (("X [mm]", "x", 0), ("Y [mm]", "y", 0),
                                   ("Width / ΔX [mm]", "w", 1), ("Height / ΔY [mm]", "h", 1),
                                   ("Rotation [°]", "angle", 0), ("Scale factor", "scale", 1),
                                   ("Force X [N]", "fx", 0), ("Force Y [N]", "fy", -1)):
            field = _number(value)
            form.addRow(label, field)
            self.fields[key] = field
        self.axes = {}
        axes = QWidget()
        row = QHBoxLayout(axes)
        for axis in ("x", "y"):
            check = QCheckBox(axis.upper())
            row.addWidget(check)
            self.axes[axis] = check
        form.addRow("Fix displacement", axes)
        self.case = QSpinBox()
        self.case.setRange(1, 100)
        form.addRow("Load case", self.case)
        self.apply_button = QPushButton("Apply object changes")
        self.apply_button.clicked.connect(self.apply_inspector)
        form.addRow(self.apply_button)
        actions = QHBoxLayout()
        for title, fn in (("Duplicate", self.duplicate), ("Delete", self.delete_selected)):
            button = QPushButton(title)
            button.clicked.connect(fn)
            actions.addWidget(button)
        form.addRow(actions)
        controls.addWidget(self.object_form)
        self.domain_form = QWidget()
        domain = QFormLayout(self.domain_form)
        self.domain_fields = {}
        for label, key, value in (("Width [mm]", "Lx", 100), ("Height [mm]", "Ly", 50),
                                   ("Young's modulus", "E0", 1), ("Poisson ratio", "nu", .3)):
            field = _number(value)
            if key != "nu":
                field.setMinimum(0.000001)
            else:
                field.setRange(-0.99, 0.499)
            domain.addRow(label, field)
            self.domain_fields[key] = field
        apply_domain = QPushButton("Apply domain / material")
        apply_domain.clicked.connect(self.apply_domain)
        domain.addRow(apply_domain)
        controls.addWidget(QLabel("Domain and physical material"))
        controls.addWidget(self.domain_form)
        controls.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inspector)
        scroll.setMinimumWidth(260)
        body.addWidget(scroll)
        body.setSizes([800, 280])
        layout.addWidget(body, 1)
        self.coordinates = QLabel("XY plane · millimetres")
        layout.addWidget(self.coordinates)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setStyleSheet("color: #d9ac6c;")
        layout.addWidget(self.validation)
        self.view.placed.connect(self._place)
        self.view.cursor_position.connect(lambda x, y: self.coordinates.setText(f"X {x:.3f} mm    Y {y:.3f} mm"))
        self.view.scene().selectionChanged.connect(self._scene_selection)
        self.object_list.currentItemChanged.connect(self._list_selection)
        self.role.currentIndexChanged.connect(self._role_fields)

    def load(self, scenario, objects, readonly=False):
        """Display an explicit scene or the actual geometry of a legacy benchmark."""
        scenario = replace(scenario, regions=None)
        shown = deepcopy(objects) if objects is not None else objects_from_scenario(scenario)
        if scenario == self.scenario and shown == self.objects and readonly == self.readonly:
            return
        self.scenario, self.objects, self.readonly = scenario, shown, readonly
        self._undo, self._redo = [], []
        self._first = None
        self._rebuild()
        self.fit()

    def _rebuild(self, selected=None):
        """Refresh both views together, retaining selection by identity."""
        self._loading = True
        scene = self.view.scene()
        scene.clear()
        self._items = {}
        self.object_list.clear()
        if self.scenario is not None:
            boundary = QGraphicsRectItem(0, -self.scenario.Ly, self.scenario.Lx, self.scenario.Ly)
            boundary.setPen(QPen(QColor("#637d91"), 0))
            boundary.setBrush(QColor("#243341"))
            boundary.setZValue(-1)
            scene.addItem(boundary)
            for key, field in self.domain_fields.items():
                field.setValue(getattr(self.scenario, key))
        for obj in self.objects:
            item = GeometryItem(obj, self.move_object, self.readonly)
            scene.addItem(item)
            self._items[obj["id"]] = item
            row = QListWidgetItem(f"{obj['name']} · {obj['role']}")
            row.setData(Qt.UserRole, obj["id"])
            self.object_list.addItem(row)
            if obj["id"] == selected:
                item.setSelected(True)
                self.object_list.setCurrentItem(row)
        self._loading = False
        for button in self.tool_buttons[2:]:
            button.setEnabled(not self.readonly)
        self.domain_form.setEnabled(not self.readonly)
        self.undo_button.setEnabled(bool(self._undo) and not self.readonly)
        self.redo_button.setEnabled(bool(self._redo) and not self.readonly)
        self.hint.setText("Reference problem · use File → Copy benchmark to custom problem to edit." if self.readonly
                          else "Select a tool, then click the canvas. Lines and rectangles use two clicks. Shapes are defined in mm.")
        self._show_inspector()

    def selected_id(self):
        """Return the selected object's stable identity, independent of list order."""
        current = self.object_list.currentItem()
        return current.data(Qt.UserRole) if current else None

    def select(self, identity):
        """Select the same definition in both the scene and object list."""
        self._loading = True
        for key, item in self._items.items():
            item.setSelected(key == identity)
        for i in range(self.object_list.count()):
            item = self.object_list.item(i)
            if item.data(Qt.UserRole) == identity:
                self.object_list.setCurrentItem(item)
        self._loading = False
        self._show_inspector()

    def _scene_selection(self):
        if not self._loading:
            selected = [item.obj["id"] for item in self.view.scene().selectedItems() if isinstance(item, GeometryItem)]
            if selected:
                self.select(selected[0])
            else:
                self.object_list.setCurrentRow(-1)
                self._show_inspector()

    def _list_selection(self, current, _previous):
        if not self._loading and current is not None:
            self.select(current.data(Qt.UserRole))

    def _show_inspector(self):
        obj = next((o for o in self.objects if o["id"] == self.selected_id()), None)
        self.object_form.setEnabled(obj is not None and not self.readonly)
        if obj is None:
            return
        self.name.setText(obj["name"])
        self.role.setCurrentIndex(self.role.findData(obj["role"]))
        for key, value in {"x": obj["position"][0], "y": obj["position"][1],
                           "w": obj["size"][0], "h": obj["size"][1], "angle": obj["rotation"][2],
                           "scale": 1, "fx": obj["force"][0], "fy": obj["force"][1]}.items():
            self.fields[key].setValue(value)
        for axis, check in self.axes.items():
            check.setChecked(axis in obj["axes"])
        self.case.setValue(obj["case"] + 1)
        self._role_fields()

    def _role_fields(self):
        for key in ("fx", "fy"):
            self.fields[key].setEnabled(self.role.currentData() == "load")
        self.case.setEnabled(self.role.currentData() == "load")
        for check in self.axes.values():
            check.setEnabled(self.role.currentData() == "support")

    def _snapshot(self):
        return self.scenario, deepcopy(self.objects)

    def _commit(self, before, selected=None):
        if self.readonly:
            return
        self._undo.append(before)
        self._redo.clear()
        self._rebuild(selected)
        self.changed.emit(self.scenario, deepcopy(self.objects))

    def set_tool(self, tool):
        """Choose a placement tool or return to selection/pan."""
        self._first = None
        self.view.tool = tool
        self.view.setDragMode(QGraphicsView.ScrollHandDrag if tool == "pan" else QGraphicsView.RubberBandDrag)
        self.hint.setText(f"{tool.title()}: click to place." + (" Click a second point to finish." if tool in {"line", "rectangle"} else ""))

    def _place(self, x, y):
        if self.readonly:
            return
        tool = self.view.tool
        if tool in {"line", "rectangle"}:
            if self._first is None:
                self._first = (x, y)
                self.hint.setText("Click the second endpoint / opposite corner.")
                return
            a, b = self._first
            self._first = None
            if tool == "rectangle":
                x, y, size = min(a, x), min(b, y), (abs(x - a), abs(y - b), 1)
            else:
                x, y, size = a, b, (x - a, y - b, 0)
        else:
            size = (self.scenario.Lx / 10, self.scenario.Lx / 10, 1)
        role = "support" if tool in {"point", "line"} else "void"
        self.add_object(make_object(tool, (x, y, 0), size, role))
        self.set_tool("select")

    def add_object(self, obj):
        """Add a physical definition, retaining its own role and stable identity."""
        if self.readonly:
            return
        before = self._snapshot()
        self.objects.append(deepcopy(obj))
        self._commit(before, obj["id"])

    def move_object(self, identity, x, y):
        """Commit a canvas drag as a physical translation."""
        if self.readonly:
            return
        before = self._snapshot()
        obj = next(o for o in self.objects if o["id"] == identity)
        obj["position"][:2] = [x, y]
        self._commit(before, identity)

    def apply_inspector(self):
        """Apply exact coordinates, role, transforms and force together."""
        if self.readonly or self.selected_id() is None:
            return
        before = self._snapshot()
        obj = next(o for o in self.objects if o["id"] == self.selected_id())
        obj["name"] = self.name.text().strip() or obj["shape"].title()
        obj["role"] = self.role.currentData()
        obj["position"][:2] = [self.fields[k].value() for k in ("x", "y")]
        scale = self.fields["scale"].value()
        obj["size"][:2] = [self.fields[k].value() * scale for k in ("w", "h")]
        obj["rotation"][2] = self.fields["angle"].value()
        obj["force"][:2] = [self.fields[k].value() for k in ("fx", "fy")]
        obj["axes"] = [axis for axis, check in self.axes.items() if check.isChecked()]
        obj["case"] = self.case.value() - 1
        self._commit(before, obj["id"])

    def apply_domain(self):
        """Change domain dimensions and material without moving physical objects."""
        if not self.readonly:
            before = self._snapshot()
            self.scenario = replace(self.scenario, **{key: field.value() for key, field in self.domain_fields.items()})
            self._commit(before)
            self.fit()

    def duplicate(self):
        """Copy a selected definition with a fresh identity."""
        from uuid import uuid4
        if self.readonly or self.selected_id() is None:
            return
        obj = deepcopy(next(o for o in self.objects if o["id"] == self.selected_id()))
        obj["id"], obj["name"] = uuid4().hex, obj["name"] + " copy"
        self.add_object(obj)

    def delete_selected(self):
        """Delete the selected object; undo restores its complete definition."""
        if not self.readonly and self.selected_id() is not None:
            before = self._snapshot()
            self.objects = [o for o in self.objects if o["id"] != self.selected_id()]
            self._commit(before)

    def undo(self):
        """Restore the previous physical definition."""
        if self._undo and not self.readonly:
            self._redo.append(self._snapshot())
            self.scenario, self.objects = self._undo.pop()
            self._rebuild()
            self.changed.emit(self.scenario, deepcopy(self.objects))

    def redo(self):
        """Reapply an undone physical definition."""
        if self._redo and not self.readonly:
            self._undo.append(self._snapshot())
            self.scenario, self.objects = self._redo.pop()
            self._rebuild()
            self.changed.emit(self.scenario, deepcopy(self.objects))

    def fit(self):
        """Show the whole domain and all geometry without distorting its aspect ratio."""
        bounds = self.view.scene().itemsBoundingRect()
        margin = max(bounds.width(), bounds.height(), 1) * .08
        bounds = bounds.adjusted(-margin, -margin, margin, margin)
        self.view.setSceneRect(bounds)
        self.view.fitInView(bounds, Qt.KeepAspectRatio)


def _number(value):
    """Numeric entry in physical units with enough precision for geometry edits."""
    field = QDoubleSpinBox()
    field.setDecimals(6)
    field.setRange(-1e7, 1e7)
    field.setValue(value)
    return field
