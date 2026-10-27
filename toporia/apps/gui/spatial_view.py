# apps/gui/spatial_view.py — optional VTK/Qt viewport over the shared physical objects.
# Numerical geometry remains in framework/problem/regions.py; this view only
# renders, picks and emits edits. QtInteractor is created lazily when shown.

import importlib.util
from copy import deepcopy

import numpy as np
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from toporia.framework.problem.spatial import rotation_matrix, triangle_mesh

COLOURS = {"support": "#49a5db", "load": "#f87777", "solid": "#c2cad3", "void": "#e1bc66", "domain": "#82cfa0"}


def object_mesh(obj, marker_size=0.2):
    """Create a display mesh with exactly the same coordinate convention as meshing."""
    import pyvista as pv
    if obj["shape"] == "stl":
        return triangle_mesh(obj)
    w, h, d = obj["size"]
    shape = obj["shape"]
    extrusion = obj.get("extrusion")
    if shape == "point":
        mesh = (pv.Line((0, 0, 0), (0, 0, extrusion)).tube(radius=marker_size / 3)
                if extrusion else pv.Sphere(radius=marker_size))
    elif shape == "line":
        mesh = pv.Line((0, 0, 0), (w, h, d))
        mesh = mesh.extrude((0, 0, extrusion)) if extrusion else mesh.tube(radius=marker_size / 3)
    elif shape == "box":
        if sum(v > 0 for v in (w, h, d)) == 2:
            import itertools
            axis = next(i for i, v in enumerate((w, h, d)) if v == 0)
            remaining = [i for i in range(3) if i != axis]
            points = np.zeros((4, 3))
            for i, corner in enumerate(itertools.product((0, 1), repeat=2)):
                points[i, remaining] = np.array(corner) * np.array((w, h, d))[remaining]
            mesh = pv.PolyData(points, [4, 0, 1, 3, 2])
        else:
            mesh = pv.Box(bounds=(0, w, 0, h, 0, d))
    elif shape == "sphere":
        mesh = pv.Sphere(radius=.5).scale((w, h, d), inplace=False)
    elif shape == "cylinder":
        mesh = pv.Cylinder(center=(0, 0, d / 2), direction=(0, 0, 1), radius=.5, height=d).scale((w, h, 1), inplace=False)
    elif shape == "rectangle":
        mesh = pv.Plane(center=(w / 2, h / 2, 0), direction=(0, 0, 1), i_size=w, j_size=h)
    elif shape == "circle":
        mesh = pv.Disc(inner=obj.get("inner_radius", 0) / (w / 2), outer=1, c_res=64).scale((w / 2, h / 2, 1), inplace=False)
    elif shape == "polygon":
        points = np.array([[x * w, y * h, 0] for x, y in obj["vertices"]])
        mesh = pv.PolyData(points, [len(points), *range(len(points))]).triangulate()
    else:
        raise ValueError(f"Unknown display shape {shape!r}")
    if extrusion and shape in {"rectangle", "circle", "polygon"}:
        mesh = mesh.extrude((0, 0, extrusion), capping=True)
    mesh.points = np.asarray(mesh.points) @ rotation_matrix(obj["rotation"]).T + np.asarray(obj["position"])
    return mesh


def transformed_object(obj, matrix):
    """Convert an actor's affine delta back into physical position/rotation/size."""
    from scipy.spatial.transform import Rotation
    matrix = np.asarray(matrix, float)
    rotation = matrix[:3, :3] @ rotation_matrix(obj["rotation"])
    scales = np.linalg.norm(rotation, axis=0)
    if np.any(scales <= 0):
        raise ValueError("Scale must stay positive")
    rotation /= scales
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6) or np.linalg.det(rotation) <= 0:
        raise ValueError("Shear and reflection are unsupported; use position, rotation and positive scale")
    edited = deepcopy(obj)
    edited["position"] = (matrix[:3, :3] @ np.asarray(obj["position"]) + matrix[:3, 3]).tolist()
    edited["size"] = (np.asarray(obj["size"]) * scales).tolist()
    edited["rotation"] = Rotation.from_matrix(rotation).as_euler("xyz", degrees=True).tolist()
    if obj.get("extrusion"):
        edited["extrusion"] = obj["extrusion"] * scales[2]
    return edited


class SpatialView(QWidget):
    """Orbit/pan/zoom, object picking, working-plane placement and transform gizmos."""

    selected = Signal(str)
    placed = Signal(object)
    transformed = Signal(object)
    camera_changed = Signal(object)
    diagnostic = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plotter = None
        self._initializing = False
        self.scenario, self.objects, self.readonly = None, [], True
        self.actors = {}
        self.identity = None
        self.gizmo = None
        self.tool = "select"
        self.workplane_z = 0
        self.camera = None
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.placeholder = QLabel("3D viewport loads when shown. Optional dependencies: pip install -e '.[gui3d]'")
        self.placeholder.setWordWrap(True)
        self.layout_box.addWidget(self.placeholder)

    def showEvent(self, event):
        super().showEvent(event)
        # Offscreen form tests exercise data/state without requiring a GPU context.
        if self.plotter is None and not self._initializing and QApplication.platformName() != "offscreen":
            self._initializing = True
            QTimer.singleShot(0, self._initialize)

    def _initialize(self):
        """Create VTK after the Qt show/layout event finishes, guarding reentrancy."""
        try:
            if importlib.util.find_spec("pyvistaqt") is None:
                return
            import os
            os.environ.setdefault("QT_API", "pyside6")
            from pyvistaqt import QtInteractor
            self.plotter = QtInteractor(self, auto_update=False)
            self.layout_box.addWidget(self.plotter.interactor)
            self.placeholder.hide()
            self.plotter.set_background("#17212b")
            self.plotter.iren.add_observer("EndInteractionEvent", lambda *_: self._camera_changed())
            self.draw()
        except (RuntimeError, AttributeError, ValueError) as error:
            self.placeholder.setText(f"Cannot initialize the 3D viewport: {error}")
            self.placeholder.show()
            self.diagnostic.emit(str(error))
        finally:
            self._initializing = False

    def load(self, scenario, objects, readonly):
        """Update definitions without creating a native renderer in a hidden workspace."""
        self.scenario, self.objects, self.readonly = scenario, deepcopy(objects), readonly
        self.draw()

    def draw(self):
        """Recreate actors while retaining camera and object selection."""
        if self.plotter is None or self.scenario is None:
            return
        import pyvista as pv
        camera = self.plotter.camera_position if self.actors else self.camera
        self._remove_gizmo()
        self.plotter.clear_camera_widgets()
        self.plotter.clear()
        self.actors = {}
        domain = pv.Box(bounds=(0, self.scenario.Lx, 0, self.scenario.Ly, 0, self.scenario.Lz))
        self.plotter.add_mesh(domain, style="wireframe", color="#748da2", pickable=False, name="domain-boundary")
        marker = max(self.scenario.Lx, self.scenario.Ly, self.scenario.Lz) * .012
        for obj in self.objects:
            try:
                mesh = object_mesh(obj, marker)
                actor = self.plotter.add_mesh(mesh, name="object:" + obj["id"], color=COLOURS[obj["role"]],
                                              opacity=.5 if obj["role"] in {"void", "domain"} else .85,
                                              show_edges=True, pickable=True)
                self.actors[obj["id"]] = actor
                if obj["role"] == "load" and np.linalg.norm(obj["force"]):
                    arrow = pv.Arrow(start=obj["position"], direction=obj["force"], scale=marker * 6)
                    self.plotter.add_mesh(arrow, color=COLOURS["load"], pickable=False)
            except (ValueError, RuntimeError) as error:
                self.diagnostic.emit(f"{obj['name']}: {error}")
        self.plotter.add_axes(interactive=True)
        self.plotter.add_camera_orientation_widget(animate=False)
        self.plotter.show_bounds(grid=False, location="outer", xtitle="X [mm]", ytitle="Y [mm]", ztitle="Z [mm]",
                                 color="#adc1d3", font_size=10, bold=False, fmt="%.1f")
        if camera is not None:
            self.plotter.camera_position = camera
        else:
            self.plotter.view_isometric()
            self.plotter.reset_camera()
        self.set_tool(self.tool)
        self.select(self.identity)
        self.plotter.render()

    def _picked(self, actor):
        for identity, candidate in self.actors.items():
            if actor is candidate or actor == candidate:
                self.selected.emit(identity)
                return

    def set_tool(self, tool):
        """Use an XY placement plane for creation; numeric Z stays independently editable."""
        self.tool = tool
        if self.plotter is None or self.scenario is None:
            return
        import pyvista as pv
        self.plotter.disable_picking()
        self.plotter.enable_custom_trackball_style(left="pan" if tool == "pan" else "rotate")
        self.plotter.remove_actor("placement-plane", render=False)
        if tool in {"select", "pan"} or self.readonly:
            self.plotter.enable_mesh_picking(callback=self._picked, use_actor=True, show=False,
                                             show_message=False, left_clicking=True)
        else:
            self._remove_gizmo()
            plane = pv.Plane(center=(self.scenario.Lx / 2, self.scenario.Ly / 2, self.workplane_z),
                             direction=(0, 0, 1), i_size=self.scenario.Lx, j_size=self.scenario.Ly)
            self.plotter.add_mesh(plane, name="placement-plane", color="#91b7c9", opacity=.15, pickable=True)
            self.plotter.enable_point_picking(callback=lambda point: self.placed.emit(list(point)),
                                              picker="cell", left_clicking=True, show_message=False, show_point=False)
        self.plotter.render()

    def select(self, identity):
        """Highlight the selected object and attach the built-in translation/rotation gizmo."""
        self.identity = identity
        if self.plotter is None:
            return
        self._remove_gizmo()
        for key, actor in self.actors.items():
            actor.prop.line_width = 4 if key == identity else 1
            actor.prop.edge_color = "white" if key == identity else "#263543"
        if identity in self.actors and not self.readonly and self.tool in {"select", "pan"}:
            obj = next(o for o in self.objects if o["id"] == identity)

            def released(matrix):
                try:
                    edited = transformed_object(obj, matrix)
                    QTimer.singleShot(0, lambda: self.transformed.emit(edited))
                except ValueError as error:
                    self.diagnostic.emit(str(error))
                    QTimer.singleShot(0, self.draw)

            actor = self.actors[identity]
            scale = max(self.scenario.Lx, self.scenario.Ly, self.scenario.Lz) * .12 / max(actor.length, .001)
            self.gizmo = self.plotter.add_affine_transform_widget(actor, origin=obj["position"], scale=scale,
                                                                  release_callback=released)
        self.plotter.render()

    def _remove_gizmo(self):
        if self.gizmo is not None:
            self.gizmo.remove()
            self.gizmo = None

    def fit(self):
        """Reset the camera to include the domain and all objects."""
        if self.plotter is not None:
            self.plotter.reset_camera()
            self.plotter.render()
            self._camera_changed()

    def camera_view(self, plane):
        """Standard orthographic/isometric camera views beside the view cube."""
        if self.plotter is not None:
            getattr(self.plotter, "view_" + plane)()
            self._camera_changed()

    def restore_camera(self, camera):
        """Apply a different project's saved camera instead of retaining the previous one."""
        self.camera = camera
        if self.plotter is not None:
            if camera is None:
                self.plotter.view_isometric()
                self.plotter.reset_camera()
            else:
                self.plotter.camera_position = camera

    def _camera_changed(self):
        if self.plotter is not None:
            self.camera = [list(vector) for vector in self.plotter.camera_position]
            self.camera_changed.emit(self.camera)

    def shutdown(self):
        """Release the VTK window on application close."""
        if self.plotter is not None:
            self._remove_gizmo()
            self.plotter.close()
            self.plotter = None
