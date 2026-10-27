# apps/gui/canvas.py — the live visualisation panel
#
# LiveCanvas is a matplotlib figure embedded directly inside the Qt window.
# It has two subplots:
#   Left  (2/3 width): density field — greyscale image of the current bracket topology
#   Right (1/3 width): convergence curve — compliance change vs iteration number
#
# The canvas is updated after every optimisation step via refresh().
# For sweep results, show_grid() loads the assembled PNG from disk and displays it.
# Before a run, show_problem() draws the problem as it is set up (apps/gui/preview.py).

import textwrap

import matplotlib.image as mpimg
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QSizePolicy

from toporia.framework.problem.mesh import projection


class LiveCanvas(FigureCanvas):
    """The live view: the current design on the left, the objective's convergence on the right."""
    # FigureCanvas is a Qt widget that contains a matplotlib figure.
    # By inheriting from it, LiveCanvas IS a Qt widget and can be added to layouts.

    def __init__(self, parent=None):
        # Create the matplotlib figure with two side-by-side subplots.
        # width_ratios=[2,1] makes the density panel twice as wide as the curve panel.
        # Embedded canvases belong to Qt, not pyplot's global figure registry.
        fig = Figure(figsize=(10, 4))
        axes = fig.subplots(1, 2, gridspec_kw={"width_ratios": [2, 1]})
        super().__init__(fig)           # give the figure to the Qt widget base class
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # fill available space
        self._fig = fig
        self._ax_d, self._ax_c = axes   # density axis, convergence axis
        self._im   = None               # the imshow image object (created on first refresh)
        self._line = None               # the convergence line object
        self.showing_problem = False    # True while the problem preview is shown instead of a run
        from .display_options import DEFAULTS
        self.options = dict(DEFAULTS)
        self.objective_label = "Objective"
        self._latest = None
        self._volumes = {}
        self._setup()

    # ── Internal colour helpers ───────────────────────────────────────────────

    def _colours(self):
        from PySide6.QtWidgets import QApplication
        if QApplication.instance().property("appearance") == "sleek":
            return "#000000", "#ffffff", "#ffffff"
        # Read the Qt window background colour from the widget's own palette.
        # This ensures the canvas blends in regardless of system theme.
        qc  = QApplication.instance().palette().color(QPalette.ColorRole.Window)
        # Perceived luminance formula (standard weighted sum of RGB channels).
        lum = 0.299*qc.redF() + 0.587*qc.greenF() + 0.114*qc.blueF()
        bg  = qc.name()                            # background as hex string, e.g. "#f0f0f0"
        tc  = "#222" if lum > 0.5 else "#ddd"      # text colour: dark on light bg, light on dark
        lc  = "#1565c0" if lum > 0.5 else "#4fc3f7" # line colour: blue shade matched to theme
        return bg, tc, lc

    def _setup(self):
        # Apply background and text colours to the figure and both axes,
        # then create placeholder plot objects that refresh() will update later.
        bg, tc, lc = self._colours()
        self._fig.patch.set_facecolor(bg)
        for ax in (self._ax_d, self._ax_c):
            ax.set_facecolor(bg)
            ax.tick_params(colors=tc)
            for sp in ax.spines.values():   # "spines" are the four border lines of an axis
                sp.set_edgecolor(tc)
        self._ax_d.axis("off")              # no tick marks on the density image
        self._ax_d.set_title("Density field", color=tc, fontsize=10)
        self._ax_c.set_title(self.objective_label, color=tc, fontsize=10)
        self._ax_c.set_xlabel("Iteration", color=tc, fontsize=9)
        self._ax_c.set_ylabel(self.objective_label.split(" (")[0], color=tc, fontsize=9)
        self._line, = self._ax_c.plot([], [], color=lc, linewidth=1.5)  # empty line to start
        self._volume_axis = self._ax_c.twinx()
        self._volume_axis.set_ylabel("Volume fraction", color=tc, fontsize=9)
        self._volume_axis.tick_params(colors=tc)
        self._volume_axis.set_ylim(0, 1)
        self._volume_line, = self._volume_axis.plot([], [], color="#8c8c8c", linestyle="--", marker=".", markersize=3)
        self._apply_graph_visibility()
        self._fig.tight_layout(pad=2.0)
        self._im = None   # reset so the next refresh() creates a fresh imshow object

    # ── Public methods called by the window ───────────────────────────────────

    def showEvent(self, event):
        """Use the final inherited Qt palette after the canvas is parented/shown."""
        super().showEvent(event)
        self.refresh_appearance()

    def refresh_appearance(self):
        if self.showing_problem and hasattr(self, "_problem_context"):
            self.show_problem(*self._problem_context)
            return
        bg, tc, lc = self._colours()
        self._fig.patch.set_facecolor(bg)
        for axis in self._fig.axes:
            axis.set_facecolor(bg)
            axis.tick_params(colors=tc)
            axis.title.set_color(tc)
            axis.xaxis.label.set_color(tc)
            axis.yaxis.label.set_color(tc)
            for spine in axis.spines.values():
                spine.set_edgecolor(tc)
        if self._line is not None:
            self._line.set_color(lc)
        if hasattr(self, "_volume_line"):
            self._volume_line.set_color("#aaaaaa" if bg == "#000000" else "#777777")
        if self._im is not None:
            self._im.set_cmap("gray_r" if bg == "#000000" else "gray")
        self.draw_idle()

    def show_problem(self, scenario, m, name=""):
        """Draw the problem as set up — domain, holes, supports, loads — filling the whole canvas."""
        from .preview import describe_problem, draw_problem
        self._problem_context = (scenario, m, name)

        bg, tc, _ = self._colours()
        self._fig.clf()
        self._fig.patch.set_facecolor(bg)
        ax = self._fig.add_subplot(1, 1, 1)
        ax.set_facecolor(bg)
        draw_problem(ax, scenario, tc, describe_problem(scenario, m, name))
        self._fig.tight_layout(pad=1.5)
        self._ax_d = ax
        self.showing_problem = True
        self.draw_idle()

    def reset(self):
        """Wipe both panels and redraw blank axes — called before each new run.
        Always rebuilds from clf() so it works even after show_grid() cleared the figure."""
        self.showing_problem = False
        self._latest = None
        self._volumes = {}
        self._fig.clf()
        axes = self._fig.subplots(1, 2, gridspec_kw={"width_ratios": [2, 1]})
        self._ax_d, self._ax_c = axes
        self._im   = None
        self._line = None
        self._setup()
        self.draw_idle()

    def refresh(self, density, objectives, iteration):
        """Update the density image and convergence curve with the latest data.
        Called once per optimisation iteration from window.py's on_iter callback."""
        if self.showing_problem or self._line is None or getattr(self._ax_d, "name", "") == "3d":
            self.reset()
        _, tc, _ = self._colours()
        self._latest = (np.asarray(density).copy(), list(objectives), iteration)
        self._volumes[iteration] = float(np.mean(density))

        # Flip the array vertically so element (0,0) appears at the bottom-left,
        # matching engineering convention (origin at lower-left).
        # Invert values (1 - density) so solid material shows dark, void shows light.
        disp = np.flipud(1.0 - projection(density))     # a 3-D design: its depth average

        if self._im is None:
            # First call: create the image object inside the axis.
            # aspect="equal" ensures pixels are square regardless of window size.
            self._im = self._ax_d.imshow(disp, cmap="gray_r" if self._colours()[0] == "#000000" else "gray", vmin=0, vmax=1,
                                          interpolation="nearest", aspect="equal")
        else:
            # Subsequent calls: update the existing image data in place (faster than
            # destroying and recreating the imshow object every iteration).
            self._im.set_data(disp)
            self._im.set_extent([0, disp.shape[1], 0, disp.shape[0]])

        seen = "  (depth average)" if np.ndim(density) == 3 else ""
        self._ax_d.set_title(self._stat_title(density, objectives, iteration) + seen, color=tc, fontsize=10)

        self._line.set_data(range(1, len(objectives) + 1), objectives)
        self._volume_line.set_data(list(self._volumes), list(self._volumes.values()))
        self._ax_c.relim()
        self._ax_c.autoscale_view()
        self._volume_axis.relim()
        self._volume_axis.autoscale_view(scaley=False)
        self.draw_idle()

    def _stat_title(self, density, objectives, iteration):
        values = []
        if self.options["iteration"]:
            values.append(f"Iteration {iteration}")
        if self.options["volume"]:
            values.append(f"Volume fraction {density.mean():.1%}")
        if self.options["objective"] and len(objectives):
            values.append(f"{self.objective_label}: {objectives[-1]:.5g}")
        # Keep metric values readable when the result panel is narrow.
        if len(values) == 3:
            return " · ".join(values[:2]) + "\n" + textwrap.fill(values[2], 65)
        return "\n".join(textwrap.fill(value, 65) for value in values)

    def set_display(self, options, objective_label=None):
        self.options = dict(options)
        if objective_label is not None:
            self.objective_label = objective_label
        if self._line is not None and not self.showing_problem:
            self._ax_c.set_ylabel(self.objective_label.split(" (")[0])
            self._apply_graph_visibility()
            if self._latest is not None:
                if getattr(self._ax_d, "name", "") == "3d":
                    self._ax_d.set_title(self._stat_title(*self._latest), color=self._colours()[1], fontsize=10)
                else:
                    self.refresh(*self._latest)
            self.draw_idle()

    def _apply_graph_visibility(self):
        objective = self.options["objective_graph"]
        volume = self.options["volume_graph"]
        self._ax_c.set_visible(objective or volume)
        self._line.set_visible(objective)
        self._volume_axis.set_visible(volume)
        self._ax_c.yaxis.set_visible(objective)
        title = self.objective_label if objective else "Volume fraction"
        self._ax_c.set_title(textwrap.fill(title, 28), color=self._colours()[1], fontsize=10)
        # Stable positions avoid a costly layout calculation on every frame.
        self._ax_d.set_position([.035, .12, .57 if objective or volume else .93, .78])
        self._ax_c.set_position([.71, .17, .2, .65])
        self._volume_axis.set_position(self._ax_c.get_position())

    def show_3d(self, density, element_size=1.0, log=print, level=0.5):
        """Replace the density image by a shaded 3-D surface of the final design (the density = `level` surface).

        Uses scikit-image's marching cubes; without it the depth average stays
        and `log` says how to get the 3-D view.
        """
        try:
            from skimage.measure import marching_cubes
        except ImportError:
            log("3-D view: pip install scikit-image to see the design in 3-D; showing its depth average.")
            return
        _, tc, _ = self._colours()
        volume = np.pad(np.asarray(density, dtype=float), 1)          # closed at the domain's faces
        if volume.max() < level or volume.min() > level:
            return
        verts, faces, _, _ = marching_cubes(volume, level=level, spacing=(element_size,) * 3)
        z, y, x = (verts - element_size).T                              # undo the padding
        spec = self._ax_d.get_subplotspec()
        self._ax_d.remove()
        ax = self._fig.add_subplot(spec, projection="3d")
        ax.set_facecolor(self._colours()[0])
        ax.plot_trisurf(x, z, faces, y, color="0.62", shade=True, linewidth=0, antialiased=True)
        nz, ny, nx = np.shape(density)
        ax.set_box_aspect((nx, nz, ny))
        ax.set_xlim(0, nx * element_size)
        ax.set_ylim(0, nz * element_size)
        ax.set_zlim(0, ny * element_size)
        ax.view_init(elev=22, azim=-62)
        ax.set_axis_off()
        ax.set_title(self._stat_title(*self._latest) if self._latest is not None else "3-D design", color=tc, fontsize=10)
        self._ax_d, self._im = ax, None
        self._apply_graph_visibility()
        self.draw_idle()

    def show_grid(self, path, title=""):
        """Display a PNG at the end of a sweep or comparison run.
        The axis fills the entire figure; aspect='equal' keeps pixels perfectly
        square — if the image and canvas proportions differ, neutral background
        shows on the shorter sides (letterbox) rather than distorting the image."""
        _, tc, _ = self._colours()
        img = mpimg.imread(str(path))
        self._fig.clf()
        ax = self._fig.add_axes([0.0, 0.0, 1.0, 1.0])   # fill entire figure area
        ax.set_facecolor(self._colours()[0])
        ax.imshow(img)   # default aspect="equal" — no distortion
        ax.axis("off")
        if title:
            self._fig.text(0.5, 0.004, title, ha="center", va="bottom",
                           color=tc, fontsize=8)
        # Stash refs so reset() can safely call clf() again on next run
        self._ax_d = ax
        self._ax_c = ax
        self._im   = None
        self._line = None
        self.draw_idle()
