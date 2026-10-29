# apps/gui/editor.py — 2D problem workspace: tools, geometry scene, object list and inspector.
# All edits update physical definitions together; scene selection and list selection
# share object IDs. Undo stores definitions, never mesh indices or screenshots.

from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QKeySequence, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .geometry import make_object, objects_from_scenario
from .spatial_view import SpatialView

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
            path.addPolygon(QPolygonF([QPointF(x * w, -y * h) for x, y in obj["vertices"]]))
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
        from .appearance import colours
        self.setBackgroundBrush(colours(self)["background"])
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
    copy_requested = Signal()
    view_changed = Signal(object)

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
        for tool in ("Select", "Pan", "Point", "Line", "Rectangle", "Circle", "Box", "Sphere", "Cylinder"):
            button = QToolButton()
            button.setText(tool)
            button.clicked.connect(lambda _=False, t=tool: self.set_tool(t.lower()))
            toolbar.addWidget(button)
            self.tool_buttons.append(button)
        self.import_button = QPushButton("Import geometry…")
        self.import_button.clicked.connect(self.import_geometry)
        toolbar.addWidget(self.import_button)
        toolbar.addStretch()
        self.copy_button = QPushButton("Copy to custom")
        self.copy_button.clicked.connect(self.copy_requested.emit)
        toolbar.addWidget(self.copy_button)
        for text, callback in (("Undo", self.undo), ("Redo", self.redo), ("Fit", self.fit)):
            button = QToolButton()
            button.setText(text)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
            setattr(self, text.lower() + "_button", button)
        layout.addLayout(toolbar)
        self.spatial_bar = QWidget()
        spatial_tools = QHBoxLayout(self.spatial_bar)
        spatial_tools.setContentsMargins(0, 0, 0, 0)
        spatial_tools.addWidget(QLabel("Placement plane Z [mm]"))
        self.plane_z = _number(0)
        spatial_tools.addWidget(self.plane_z)
        for title, plane in (("XY", "xy"), ("XZ", "xz"), ("YZ", "yz"), ("Isometric", "isometric")):
            button = QPushButton(title)
            button.clicked.connect(lambda _=False, p=plane: self.spatial.camera_view(p))
            spatial_tools.addWidget(button)
        spatial_tools.addStretch()
        layout.addWidget(self.spatial_bar)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        body = QSplitter()
        self.view = ProblemView()
        self.viewport_stack = QStackedWidget()
        self.viewport_stack.addWidget(self.view)
        self.spatial = SpatialView()
        self.viewport_stack.addWidget(self.spatial)
        body.addWidget(self.viewport_stack)
        self.spatial.selected.connect(self.select)
        self.spatial.placed.connect(self._place_spatial)
        self.spatial.transformed.connect(self._spatial_transform)
        self.spatial.camera_changed.connect(lambda camera: self.view_changed.emit({"camera3d": camera}))
        self.spatial.diagnostic.connect(self._diagnostic)
        self.plane_z.valueChanged.connect(self._plane_changed)
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
        self.sampling = QComboBox()
        self.sampling.addItem("Closed volume", "volume")
        self.sampling.addItem("Surface proximity", "surface")
        form.addRow("STL sampling", self.sampling)
        self.fields = {}
        self.field_labels = {}
        for label, key, value in (("X [mm]", "x", 0), ("Y [mm]", "y", 0), ("Z [mm]", "z", 0),
                                   ("Width / ΔX [mm]", "w", 1), ("Height / ΔY [mm]", "h", 1),
                                   ("Depth / ΔZ [mm]", "d", 1), ("Rotation X [°]", "rx", 0), ("Rotation Y [°]", "ry", 0),
                                   ("Rotation [°]", "angle", 0), ("Scale factor", "scale", 1),
                                   ("Force X [N]", "fx", 0), ("Force Y [N]", "fy", -1), ("Force Z [N]", "fz", 0)):
            field = _number(value)
            form.addRow(label, field)
            self.fields[key] = field
            self.field_labels[key] = form.labelForField(field)
        self.fields["scale"].setMinimum(.000001)
        self.axes = {}
        axes = QWidget()
        row = QHBoxLayout(axes)
        for axis in ("x", "y", "z"):
            check = QCheckBox(axis.upper())
            row.addWidget(check)
            self.axes[axis] = check
        form.addRow("Fix displacement", axes)
        self.case = QSpinBox()
        self.case.setRange(1, 100)
        form.addRow("Load case", self.case)
        self.object_form_layout = form
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
        budget_note = QLabel("Material budget is measured against the bounding grid; excluded cells count as empty.")
        budget_note.setWordWrap(True)
        budget_note.setStyleSheet("font-size: 11px;")
        controls.addWidget(budget_note)
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
        layout.addWidget(self.validation)
        self.view.placed.connect(self._place)
        self.view.cursor_position.connect(lambda x, y: self.coordinates.setText(f"X {x:.3f} mm    Y {y:.3f} mm"))
        self.view.scene().selectionChanged.connect(self._scene_selection)
        self.object_list.currentItemChanged.connect(self._list_selection)
        self.role.currentIndexChanged.connect(self._role_fields)
        for shortcut, callback in ((QKeySequence.Undo, self.undo), (QKeySequence.Redo, self.redo),
                                   (QKeySequence.Delete, self.delete_selected), ("Escape", lambda: self.set_tool("select"))):
            action = QAction(self)
            action.setShortcut(shortcut)
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            action.triggered.connect(callback)
            self.addAction(action)

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
            boundary.setData(0, "domain-frame")
            boundary.setPen(QPen(QColor("#637d91"), 0))
            boundary.setBrush(QColor("#243341"))
            boundary.setZValue(-1)
            scene.addItem(boundary)
            origin = scene.addSimpleText("0,0 · XY [mm]")
            origin.setData(0, "origin-label")
            origin.setBrush(QColor("#91a8ba"))
            origin.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            origin.setPos(0, 0)
            for key, field in self.domain_fields.items():
                field.setValue(getattr(self.scenario, key))
        for obj in self.objects:
            item = GeometryItem(obj, self.move_object, self.readonly)
            scene.addItem(item)
            if obj["role"] == "load":
                import numpy as np
                vector = np.asarray(obj["force"][:2], float)
                norm = np.linalg.norm(vector)
                if norm:
                    delta = vector / norm * max(self.scenario.Lx, self.scenario.Ly) * .065
                    start = QPointF(obj["position"][0], -obj["position"][1])
                    end = start + QPointF(delta[0], -delta[1])
                    arrow = QPainterPath(start)
                    arrow.lineTo(end)
                    # Arrowhead size follows domain scale, independent of force magnitude.
                    d = end - start
                    length = (d.x() ** 2 + d.y() ** 2) ** .5
                    unit = d / length
                    normal = QPointF(-unit.y(), unit.x())
                    arrow.lineTo(end - unit * length * .25 + normal * length * .13)
                    arrow.moveTo(end)
                    arrow.lineTo(end - unit * length * .25 - normal * length * .13)
                    shown = scene.addPath(arrow, QPen(QColor(COLOURS["load"]), 0))
                    shown.setAcceptedMouseButtons(Qt.NoButton)
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
        self.copy_button.setVisible(self.readonly)
        three = self.scenario is not None and self.scenario.Lz > 0
        for button in self.tool_buttons[6:]:
            button.setVisible(three)
        self.spatial_bar.setVisible(three)
        self.import_button.setEnabled(not self.readonly)
        self.viewport_stack.setCurrentIndex(1 if three else 0)
        for key in ("z", "d", "rx", "ry", "fz"):
            self.fields[key].setVisible(three)
            self.field_labels[key].setVisible(three)
        self.axes["z"].setVisible(three)
        self.coordinates.setText("XYZ · millimetres · drag to orbit, Shift+drag to pan, wheel to zoom" if three else "XY plane · millimetres")
        if three:
            self.spatial.load(self.scenario, self.objects, self.readonly)
            self.spatial.select(selected)
        self.undo_button.setEnabled(bool(self._undo) and not self.readonly)
        self.redo_button.setEnabled(bool(self._redo) and not self.readonly)
        self.hint.setText("Reference problem · use File → Copy benchmark to custom problem to edit." if self.readonly
                          else "Click the XY placement plane to create a shape, then edit XYZ values in the inspector." if three
                          else "Select a tool, then click the canvas. Lines and rectangles use two clicks. Shapes are defined in mm.")
        self._show_inspector()
        self.refresh_appearance()

    def refresh_appearance(self):
        from .appearance import colours
        colors = colours(self)
        self.view.setBackgroundBrush(colors["background"])
        for item in self.view.scene().items():
            if item.data(0) == "domain-frame":
                item.setPen(QPen(colors["border"], 0))
                item.setBrush(colors["surface"])
            elif item.data(0) == "origin-label":
                item.setBrush(colors["muted"])
        self.view.viewport().update()

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
        if self.scenario is not None and self.scenario.Lz > 0:
            self.spatial.select(identity)

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
        self.object_form.setVisible(obj is not None)
        if obj is None:
            return
        self.name.setText(obj["name"])
        self.role.setCurrentIndex(self.role.findData(obj["role"]))
        stl = obj["shape"] == "stl"
        for key, axis in (("w", "X"), ("h", "Y"), ("d", "Z")):
            self.field_labels[key].setText(f"Scale {axis}" if stl else f"Size / Δ{axis} [mm]")
        if obj.get("extrusion"):
            self.field_labels["d"].setText("Extrusion [mm]")
        self.sampling.setCurrentIndex(self.sampling.findData(obj.get("sampling", "volume")))
        self.sampling.setVisible(stl)
        self.object_form_layout.labelForField(self.sampling).setVisible(stl)
        for key, value in {"x": obj["position"][0], "y": obj["position"][1],
                           "w": obj["size"][0], "h": obj["size"][1], "angle": obj["rotation"][2],
                           "z": obj["position"][2], "d": obj["size"][2],
                           "rx": obj["rotation"][0], "ry": obj["rotation"][1],
                           "scale": 1, "fx": obj["force"][0], "fy": obj["force"][1], "fz": obj["force"][2]}.items():
            self.fields[key].setValue(value)
        for axis, check in self.axes.items():
            check.setChecked(axis in obj["axes"])
        if obj.get("extrusion"):
            self.fields["d"].setValue(obj["extrusion"])
        self.case.setValue(obj["case"] + 1)
        self._role_fields()

    def _role_fields(self):
        for key in ("fx", "fy", "fz"):
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
        if self.scenario is not None and self.scenario.Lz > 0:
            self.spatial.set_tool(tool)
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
        obj["position"] = [self.fields[k].value() for k in ("x", "y", "z")]
        scale = self.fields["scale"].value()
        original_depth = obj["size"][2]
        obj["size"] = [self.fields[k].value() * scale for k in ("w", "h", "d")]
        if self.scenario.Lz == 0:
            obj["size"][2] = self.fields["d"].value()
        obj["rotation"] = [self.fields[k].value() for k in ("rx", "ry", "angle")]
        obj["force"] = [self.fields[k].value() for k in ("fx", "fy", "fz")]
        if obj.get("extrusion"):
            obj["size"][2] = original_depth
            obj["extrusion"] = self.fields["d"].value() * scale
        if obj["shape"] == "stl":
            obj["sampling"] = self.sampling.currentData()
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
        if self.scenario is None:
            return
        if self.scenario.Lz > 0:
            self.spatial.fit()
            return
        # Screen-sized annotations must not enlarge the physical fitting bounds.
        bounds = QRectF(0, -self.scenario.Ly, self.scenario.Lx, self.scenario.Ly)
        for item in self._items.values():
            bounds = bounds.united(item.sceneBoundingRect())
        margin = max(bounds.width(), bounds.height(), 1) * .08
        bounds = bounds.adjusted(-margin, -margin, margin, margin)
        self.view.setSceneRect(bounds)
        self.view.fitInView(bounds, Qt.KeepAspectRatio)

    def _place_spatial(self, point):
        """Create a 3D primitive on the working plane, then edit its precise XYZ values."""
        if self.readonly:
            return
        tool = self.spatial.tool
        x, y, z = point
        length = min(self.scenario.Lx, self.scenario.Ly, self.scenario.Lz) / 3
        size = (length, length, length)
        if tool == "line":
            if self._first is None:
                self._first = point
                return
            size = tuple(b - a for a, b in zip(self._first, point, strict=True))
            x, y, z = self._first
            self._first = None
        if tool == "rectangle":
            size = (length, length, 0)
        role = "support" if tool in {"point", "line", "rectangle", "circle"} else "void"
        self.add_object(make_object(tool, (x, y, z), size, role, axes=["x", "y", "z"]))
        self.set_tool("select")

    def _spatial_transform(self, edited):
        """Record one completed gizmo movement as one undoable edit."""
        if not self.readonly:
            before = self._snapshot()
            self.objects = [edited if obj["id"] == edited["id"] else obj for obj in self.objects]
            self._commit(before, edited["id"])

    def _plane_changed(self, value):
        self.spatial.workplane_z = value
        self.spatial.set_tool(self.spatial.tool)

    def _diagnostic(self, text):
        self.hint.setText(text)

    def import_geometry(self, path=None):
        """Import geometry as an editable region; assign its physical role in the inspector."""
        if self.readonly:
            return
        three = self.scenario.Lz > 0
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Import geometry", "",
                                                 "STL geometry (*.stl)" if three else "DXF profile (*.dxf)")
        if not path:
            return
        try:
            from .geometry_import import import_dxf, import_stl
            objects = [import_stl(path)] if three else import_dxf(path)
            before = self._snapshot()
            self.objects.extend(objects)
            self._commit(before, objects[-1]["id"])
            self.fit()
        except (OSError, ValueError, RuntimeError) as error:
            QMessageBox.warning(self, "Cannot import geometry", str(error))


def _number(value):
    """Numeric entry in physical units with enough precision for geometry edits."""
    field = QDoubleSpinBox()
    field.setDecimals(6)
    field.setRange(-1e7, 1e7)
    field.setValue(value)
    return field
