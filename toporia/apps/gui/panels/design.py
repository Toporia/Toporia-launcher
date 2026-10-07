# apps/gui/panels/design.py — the Design section: what the design is, in how many dimensions, how finely meshed.
#
#   Representation  what the design variables are (element densities, moving
#                   morphable components, ...), with its own parameters
#   Dimensions      2-D (plane stress) or 3-D: the case's rectangle extruded to
#                   a depth (Scenario.Lz).  Switching asks the window to pick a
#                   physics model that works in that dimension (q4 <-> h8).
#   Resolution      as elements per mm, or as the size of one element in mm —
#                   the same setting (Solver.m) entered either way — with the
#                   resulting element counts shown, so the cost is visible
#                   before the run.
#
# The case itself — its size, supports and loads — stays as the preset defines it.

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from .common import CollapsibleSection, add_tooltip_row, double_box
from .specs import RepresentationGroup

#: The resolution entered as elements per mm, or as one element's size.
PER_MM, SIZE = "per_mm", "size"


class DesignSection(QWidget):
    """Representation, 2-D or 3-D with its depth, and the mesh resolution with the resulting element counts."""
    changed = Signal()
    dims_changed = Signal(int)          # 2 or 3

    def __init__(self, representations, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._section = CollapsibleSection("Design", expanded=True)
        outer.addWidget(self._section)
        self._Lx, self._Ly = 100.0, 50.0       # the case's rectangle, for the element counts

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        self.dims = QComboBox()
        self.dims.addItem("2-D (plane stress)", userData=2)
        self.dims.addItem("3-D (extruded to a depth)", userData=3)
        add_tooltip_row(form, "Dimensions", self.dims,
                        "2-D solves the case's rectangle in plane stress. 3-D extrudes it to the depth "
                        "below: holes go through, supports and loads act through the thickness.")
        self.depth = double_box(10.0, 0.1, 10000.0, dec=2, step=1.0)
        self.depth.setSuffix(" mm")
        self._depth_label = QLabel("Depth")
        self._depth_label.setToolTip("How deep the 3-D box is (Scenario.Lz).")
        form.addRow(self._depth_label, self.depth)
        self.mode = QComboBox()
        self.mode.addItem("Elements per mm", userData=PER_MM)
        self.mode.addItem("Element size (mm)", userData=SIZE)
        add_tooltip_row(form, "Resolution as", self.mode,
                        "Enter the mesh resolution as elements per mm, or as the edge length of one element.")
        self.resolution = double_box(1.0, 0.001, 1000.0, dec=3, step=0.1)
        add_tooltip_row(form, "Resolution", self.resolution,
                        "Finer meshes give finer designs but take longer, much more so in 3-D.")
        self.counts = QLabel()
        self.counts.setToolTip("The mesh this resolution gives for the case, and its number of elements.")
        form.addRow("Mesh", self.counts)
        self._section.body_layout.addWidget(form_widget)

        self.representation = RepresentationGroup(representations)
        self._section.body_layout.addWidget(self.representation)

        self.dims.currentIndexChanged.connect(self._on_dims)
        self.mode.currentIndexChanged.connect(self._on_mode)
        for signal in (self.depth.valueChanged, self.resolution.valueChanged):
            signal.connect(self._on_value)
        self.representation.changed.connect(self.changed.emit)
        self._per_mm = 1.0
        self._on_dims()

    # ── Values ────────────────────────────────────────────────────────────────

    def is_3d(self):
        """True when the 3-D option is selected."""
        return self.dims.currentData() == 3

    def elements_per_mm(self):
        """Solver.m, whichever way the resolution was entered."""
        return self._per_mm

    def get_values(self):
        """{"m": ..., "Lz": ...} to overlay on a Run: Lz is 0 in 2-D."""
        return {"m": self.elements_per_mm(), "Lz": self.depth.value() if self.is_3d() else 0.0}

    def get_spec(self):
        """The representation spec (solver.representation)."""
        return self.representation.get_spec()

    def load_spec(self, spec):
        """Show a representation spec in the representation panel."""
        self.representation.load_spec(spec)

    def load_from_config(self, cfg):
        """Show a Run's dimensions, depth, resolution and representation."""
        scenario = cfg.scenario
        self._Lx, self._Ly = scenario.Lx, scenario.Ly
        for widget in (self.dims, self.depth, self.resolution):
            widget.blockSignals(True)
        self.dims.setCurrentIndex(self.dims.findData(3 if scenario.Lz > 0 else 2))
        if scenario.Lz > 0:
            self.depth.setValue(scenario.Lz)
        else:
            self.depth.setValue(round(max(scenario.Ly / 4.0, 1.0), 1))   # a sensible depth for switching
        self._per_mm = float(cfg.solver.m)
        self._show_resolution()
        for widget in (self.dims, self.depth, self.resolution):
            widget.blockSignals(False)
        self.representation.load_spec(cfg.solver.representation)
        self._on_dims(emit=False)

    def set_representation_available(self, available):
        """Hide the representation for methods that keep their own variables (pyMOTO, the level set)."""
        self.representation.setVisible(available)

    # ── Reactions ─────────────────────────────────────────────────────────────

    def _show_resolution(self):
        self.resolution.blockSignals(True)
        if self.mode.currentData() == SIZE:
            self.resolution.setSuffix(" mm")
            self.resolution.setValue(1.0 / self._per_mm)
        else:
            self.resolution.setSuffix(" el/mm")
            self.resolution.setValue(self._per_mm)
        self.resolution.blockSignals(False)
        self._show_counts()

    def _show_counts(self):
        m = self._per_mm
        nelx, nely = int(round(self._Lx * m)), max(1, int(round(self._Ly * m)))
        if self.is_3d():
            nelz = max(1, int(round(self.depth.value() * m)))
            text = f"{nelx} × {nely} × {nelz} = {nelx * nely * nelz:,} elements"
        else:
            text = f"{nelx} × {nely} = {nelx * nely:,} elements"
        self.counts.setText(f"{text}  (element {1.0 / m:.3g} mm)")

    def _on_mode(self, *_):
        self._show_resolution()

    def _on_value(self, *_):
        value = self.resolution.value()
        if value > 0:
            self._per_mm = 1.0 / value if self.mode.currentData() == SIZE else value
        self._show_counts()
        self.changed.emit()

    def _on_dims(self, *_, emit=True):
        three = self.is_3d()
        self.depth.setVisible(three)
        self._depth_label.setVisible(three)
        self._section.set_title(f"Design ({'3-D' if three else '2-D'})")
        self._show_counts()
        if emit:
            self.dims_changed.emit(3 if three else 2)
            self.changed.emit()
