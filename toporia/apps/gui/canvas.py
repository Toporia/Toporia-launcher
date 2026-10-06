# apps/gui/canvas.py — the live visualisation panel
#
# LiveCanvas is a matplotlib figure embedded directly inside the Qt window.
# It has two subplots:
#   Left  (2/3 width): density field — greyscale image of the current bracket topology
#   Right (1/3 width): convergence curve — compliance change vs iteration number
#
# The canvas is updated after every optimisation step via refresh().
# For sweep results, show_grid() loads the assembled PNG from disk and displays it.

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
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
        fig, axes = plt.subplots(1, 2, figsize=(10, 4),
                                 gridspec_kw={"width_ratios": [2, 1]})
        super().__init__(fig)           # give the figure to the Qt widget base class
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # fill available space
        self._fig = fig
        self._ax_d, self._ax_c = axes   # density axis, convergence axis
        self._im   = None               # the imshow image object (created on first refresh)
        self._line = None               # the convergence line object
        self._setup()

    # ── Internal colour helpers ───────────────────────────────────────────────

    def _colours(self):
        # Read the Qt window background colour from the widget's own palette.
        # This ensures the canvas blends in regardless of system theme.
        qc  = self.palette().color(QPalette.ColorRole.Window)
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
        self._ax_c.set_title("Objective (Δ iter 1)", color=tc, fontsize=10)
        self._ax_c.set_xlabel("Iteration", color=tc, fontsize=9)
        self._ax_c.set_ylabel("ΔCompliance", color=tc, fontsize=9)
        self._line, = self._ax_c.plot([], [], color=lc, linewidth=1.5)  # empty line to start
        self._fig.tight_layout(pad=2.0)
        self._im = None   # reset so the next refresh() creates a fresh imshow object

    # ── Public methods called by the window ───────────────────────────────────

    def reset(self):
        """Wipe both panels and redraw blank axes — called before each new run.
        Always rebuilds from clf() so it works even after show_grid() cleared the figure."""
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
        _, tc, _ = self._colours()

        # Flip the array vertically so element (0,0) appears at the bottom-left,
        # matching engineering convention (origin at lower-left).
        # Invert values (1 - density) so solid material shows dark, void shows light.
        disp = np.flipud(1.0 - projection(density))     # a 3-D design: its depth average

        if self._im is None:
            # First call: create the image object inside the axis.
            # aspect="equal" ensures pixels are square regardless of window size.
            self._im = self._ax_d.imshow(disp, cmap="gray", vmin=0, vmax=1,
                                          interpolation="nearest", aspect="equal")
        else:
            # Subsequent calls: update the existing image data in place (faster than
            # destroying and recreating the imshow object every iteration).
            self._im.set_data(disp)
            self._im.set_extent([0, disp.shape[1], 0, disp.shape[0]])

        seen = "  (depth average)" if np.ndim(density) == 3 else ""
        self._ax_d.set_title(f"iter {iteration}  |  vol = {density.mean():.3f}{seen}",
                             color=tc, fontsize=10)

        # Plot compliance relative to the first iteration so the curve starts at 0.
        rel = [o - objectives[0] for o in objectives]  # list comprehension
        self._line.set_data(range(len(rel)), rel)
        self._ax_c.relim()          # recalculate axis limits to fit new data
        self._ax_c.autoscale_view() # apply those limits
        self._fig.tight_layout(pad=2.0)
        self.draw_idle()

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
        ax.plot_trisurf(x, z, faces, y, color="0.62", shade=True, linewidth=0, antialiased=True)
        nz, ny, nx = np.shape(density)
        ax.set_box_aspect((nx, nz, ny))
        ax.set_xlim(0, nx * element_size)
        ax.set_ylim(0, nz * element_size)
        ax.set_zlim(0, ny * element_size)
        ax.view_init(elev=22, azim=-62)
        ax.set_axis_off()
        ax.set_title(f"3-D design (density ≥ {level:g})  |  vol = {np.mean(density):.3f}", color=tc, fontsize=10)
        self._ax_d, self._im = ax, None
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
