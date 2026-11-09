# toporia_gui/canvas.py — the live visualisation panel
#
# LiveCanvas is a matplotlib figure embedded directly inside the Qt window.
# It has two subplots:
#   Left  (2/3 width): density field — greyscale image of the current bracket topology
#   Right (1/3 width): convergence curve — compliance change vs iteration number
#
# The canvas is updated after every optimisation step via refresh().
# For sweep results, show_grid() loads the assembled PNG from disk and displays it.
# Before a run, show_problem() draws the problem as it is set up (toporia_gui/preview.py).

import textwrap

import matplotlib.image as mpimg
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QSizePolicy

from toporia_core.framework.problem.mesh import projection

from .appearance import is_dark


class PanZoom:
    """Pan and zoom for a matplotlib canvas whose figure is `self._fig` (2-D axes only)."""

    def _install_pan_zoom(self):
        """Wheel zooms about the cursor, dragging pans, a double-click restores the full view.

        Connected to the canvas, so it survives every clf(). A zoomed axis turns its
        autoscaling off, so a running optimisation keeps the chosen view.
        """
        self._drag = None
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_motion)
        self.mpl_connect("button_release_event", self._on_release)

    @staticmethod
    def _flat(ax):
        return ax is not None and getattr(ax, "name", "") != "3d"

    def _on_scroll(self, event):
        ax = event.inaxes
        if not self._flat(ax) or event.xdata is None:
            return
        factor = 1 / 1.2 if event.button == "up" else 1.2
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ax.set_xlim(event.xdata + (x0 - event.xdata) * factor, event.xdata + (x1 - event.xdata) * factor)
        ax.set_ylim(event.ydata + (y0 - event.ydata) * factor, event.ydata + (y1 - event.ydata) * factor)
        self.draw_idle()

    def _on_press(self, event):
        ax = event.inaxes
        if not self._flat(ax) or event.button not in (1, 2):
            return
        if event.dblclick:
            self.reset_view(ax)
            return
        self._drag = (ax, event.x, event.y, ax.get_xlim(), ax.get_ylim())

    def _on_motion(self, event):
        if self._drag is None or event.x is None:
            return
        ax, x, y, (x0, x1), (y0, y1) = self._drag
        box = ax.get_window_extent()
        dx = (event.x - x) * (x1 - x0) / max(box.width, 1)
        dy = (event.y - y) * (y1 - y0) / max(box.height, 1)
        ax.set_xlim(x0 - dx, x1 - dx)
        ax.set_ylim(y0 - dy, y1 - dy)
        self.draw_idle()

    def _on_release(self, event):
        self._drag = None

    def reset_view(self, ax=None):
        """The whole field, or every point of the curve, again."""
        for axis in ([ax] if ax is not None else self._fig.axes):
            if not self._flat(axis):
                continue
            images = axis.get_images()
            if images:
                left, right, bottom, top = images[0].get_extent()
                axis.set_xlim(left, right)
                axis.set_ylim(bottom, top)
            else:
                axis.set_autoscale_on(True)
                axis.relim()
                axis.autoscale_view()
        self.draw_idle()


class LiveCanvas(PanZoom, FigureCanvas):
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
        self._network, self._network_width = None, None   # a truss, and the domain width in mm
        self._mesh = None                                    # a design on triangles (unstructured)
        self._overlay = []
        self._volumes = {}
        self._setup()
        self._install_pan_zoom()

    # ── Internal colour helpers ───────────────────────────────────────────────

    def _colours(self):
        from PySide6.QtWidgets import QApplication

        from .appearance import current_scheme
        scheme = current_scheme()
        if scheme is not None:
            return scheme["background"], scheme["text"], scheme["accent"]
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
            self._volume_line.set_color("#aaaaaa" if is_dark(bg) else "#777777")
        if self._im is not None:
            self._im.set_cmap("gray_r" if is_dark(bg) else "gray")
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
        self._overlay = []          # cleared with the figure
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
            self._im = self._ax_d.imshow(disp, cmap="gray_r" if is_dark(self._colours()[0]) else "gray", vmin=0, vmax=1,
                                          interpolation="nearest", aspect="equal")
        else:
            # Subsequent calls: update the existing image data in place (faster than
            # destroying and recreating the imshow object every iteration).
            self._im.set_data(disp)
            self._im.set_extent([0, disp.shape[1], 0, disp.shape[0]])

        self._draw_overlay(disp.shape)
        seen = "  (depth average)" if np.ndim(density) == 3 else ""
        if self._network and self.options.get("network", True) and self._network.get("node_label"):
            seen += f"\nnode colour: {self._network['node_label']}"
        self._ax_d.set_title(self._stat_title(density, objectives, iteration) + seen, color=tc, fontsize=10)

        self._line.set_data(range(1, len(objectives) + 1), objectives)
        self._volume_line.set_data(list(self._volumes), list(self._volumes.values()))
        self._ax_c.relim()
        self._ax_c.autoscale_view()
        self._volume_axis.relim()
        self._volume_axis.autoscale_view(scaley=False)
        self.draw_idle()

    def set_network(self, network, width=None):
        """A design of nodes and bars (a truss) to draw over the density; None removes it.

        `width` is the domain's width in mm, which places the nodes on the image.
        """
        self._network, self._network_width = network, width

    def set_mesh(self, mesh, width=None):
        """A design on a triangle mesh to draw instead of its grid sampling; None removes it."""
        self._mesh, self._network_width = mesh, (width if mesh is not None else self._network_width)

    def _draw_overlay(self, shape):
        """The design in its own representation, over the 2-D image: bars and nodes, or the elements."""
        for artist in self._overlay:
            try:
                artist.remove()
            except (ValueError, NotImplementedError):
                pass
        self._overlay = []
        if self._im is not None:
            self._im.set_alpha(1.0)
        ny, nx = shape
        if self.options.get("elements", False) and nx * ny <= 40_000:
            from matplotlib.collections import LineCollection
            edges = [[(x - 0.5, -0.5), (x - 0.5, ny - 0.5)] for x in range(nx + 1)]
            edges += [[(-0.5, y - 0.5), (nx - 0.5, y - 0.5)] for y in range(ny + 1)]
            grid = LineCollection(edges, colors=self._colours()[1], linewidths=0.3, alpha=0.35)
            self._ax_d.add_collection(grid)
            self._overlay.append(grid)
        mesh = self._mesh
        if self.options.get("network", True) and mesh and len(mesh.get("triangles") or ()):
            # The design on its own triangles, over the grid sampling the engine records.
            h = (self._network_width or nx) / nx
            nodes = np.asarray(mesh["nodes"], dtype=float)
            x, y = nodes[:, 0] / h - 0.5, ny - nodes[:, 1] / h - 0.5
            dark = is_dark(self._colours()[0])
            values = np.asarray(mesh["values"], dtype=float)
            artist = self._ax_d.tripcolor(x, y, np.asarray(mesh["triangles"], dtype=int),
                                          facecolors=values if dark else 1.0 - values, cmap="gray",
                                          vmin=0, vmax=1, edgecolors="none", zorder=2)
            self._overlay.append(artist)
            if self._im is not None:
                self._im.set_alpha(0.0)
        network = self._network
        if not (self.options.get("network", True) and network and len(network.get("nodes") or ())
                and len(network["nodes"][0]) == 2):
            return
        h = (self._network_width or nx) / nx                    # mm per element
        nodes = np.asarray(network["nodes"], dtype=float)
        pixels = np.column_stack([nodes[:, 0] / h - 0.5, ny - nodes[:, 1] / h - 0.5])
        # A truss is its bars: the density drawn for the record fades to a faint background.
        if self._im is not None:
            self._im.set_alpha(0.15)
        self._overlay += draw_network(self._ax_d, pixels, network, self._colours()[1])

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
        if self._line is None:            # a single-panel view: no curve to show or hide
            return
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

    #: At most this many elements are drawn in a density cloud; the densest are kept.
    CLOUD_LIMIT = 40_000

    def show_3d(self, density, element_size=1.0, log=print, level=0.5, cloud=None):
        """Replace the depth-averaged image by a 3-D view of the final design.

        A density cloud by default (display option "3-D designs as a cloud"): every
        element with some material, more opaque and darker the denser it is, so the
        whole field shows, not one average.  Otherwise the density = `level`
        surface, with scikit-image's marching cubes; without it the depth average
        stays and `log` says how to get the 3-D view.
        """
        if cloud if cloud is not None else self.options.get("cloud3d", True):
            self._show_cloud(np.asarray(density, dtype=float), element_size)
            return
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

    def _three_d_axes(self, shape, element_size):
        """Replace the design panel by 3-D axes for a (nz, ny, nx) field; x across, depth back, y up."""
        spec = self._ax_d.get_subplotspec()
        self._ax_d.remove()
        ax = self._fig.add_subplot(spec, projection="3d")
        ax.set_facecolor(self._colours()[0])
        nz, ny, nx = shape
        ax.set_box_aspect((nx, nz, ny))
        ax.set_xlim(0, nx * element_size)
        ax.set_ylim(0, nz * element_size)
        ax.set_zlim(0, ny * element_size)
        ax.view_init(elev=22, azim=-62)
        ax.set_axis_off()
        return ax

    def _show_cloud(self, density, element_size):
        bg, tc, _ = self._colours()
        ax = self._three_d_axes(density.shape, element_size)
        z, y, x = np.nonzero(density > 0.05)
        values = density[z, y, x]
        if values.size > self.CLOUD_LIMIT:                          # keep the densest elements
            keep = np.argsort(values)[-self.CLOUD_LIMIT:]
            z, y, x, values = z[keep], y[keep], x[keep], values[keep]
        colours = np.zeros((values.size, 4))
        ink = 0.85 if is_dark(bg) else 0.1                          # solid is light on a dark background
        shade = ink + (0.6 - ink) * (1 - values)                    # faint material drifts to mid grey
        colours[:, :3] = shade[:, None]
        colours[:, 3] = 0.03 + 0.62 * values ** 2                   # near-void almost clear, solid opaque
        size = max(2.0, (260.0 / max(density.shape)) ** 2 * 0.6)
        h = element_size
        ax.scatter((x + 0.5) * h, (z + 0.5) * h, (y + 0.5) * h, c=colours, s=size, marker="s",
                   depthshade=False, edgecolors="none")
        mesh = self._mesh
        if self.options.get("network", True) and mesh and len(mesh.get("tetrahedra") or ()):
            # A design on tetrahedra: the surface of its solid cells, which follows its holes.
            from types import SimpleNamespace

            from mpl_toolkits.mplot3d.art3d import Poly3DCollection

            from toporia_library.physics.tet_mesh import solid_surface
            cells = SimpleNamespace(nodes=np.asarray(mesh["nodes"], dtype=float),
                                    tets=np.asarray(mesh["tetrahedra"], dtype=int))
            faces = solid_surface(cells, np.asarray(mesh["values"], dtype=float))
            if len(faces):
                ax.add_collection3d(Poly3DCollection(faces[:, :, [0, 2, 1]], facecolor="0.62", edgecolor="none",
                                                     alpha=0.9))
        network = self._network
        if (self.options.get("network", True) and network and len(network.get("nodes") or ())
                and len(network["nodes"][0]) == 3):
            nodes = np.asarray(network["nodes"], dtype=float)
            draw_network(ax, nodes[:, [0, 2, 1]], network, tc)        # x, depth, height, as the cloud
        title = self._stat_title(*self._latest) if self._latest is not None else "3-D design"
        ax.set_title(title + "\n(density cloud: drag to rotate)", color=tc, fontsize=10)
        self._ax_d, self._im = ax, None
        self._apply_graph_visibility()
        self.draw_idle()

    def show_export_preview(self, density, element_size, title, outline=True):
        """What an export writes: the design at its real size, and the 0.5 outline vector formats trace.

        A 3-D design is shown as the density = 0.5 surface an STL holds.
        """
        bg, tc, lc = self._colours()
        density = np.asarray(density, dtype=float)
        self.showing_problem = False
        self._fig.clf()
        self._fig.patch.set_facecolor(bg)
        ax = self._fig.add_subplot(1, 1, 1)
        ax.set_facecolor(bg)
        self._ax_d, self._ax_c, self._im, self._line = ax, ax, None, None
        if density.ndim == 3:
            self._latest = None
            self.show_3d(density, element_size, log=lambda *_: None, cloud=False)   # the surface an STL holds
            self._ax_d.set_title(title, color=tc, fontsize=10)
            self.draw_idle()
            return
        ny, nx = density.shape
        extent = [0, nx * element_size, 0, ny * element_size]
        ax.imshow(np.flipud(1.0 - density), cmap="gray_r" if is_dark(bg) else "gray", vmin=0, vmax=1,
                  interpolation="nearest", extent=extent, aspect="equal")
        if outline and density.min() < 0.5 <= density.max():
            xs = (np.arange(nx) + 0.5) * element_size
            ys = (np.arange(ny) + 0.5) * element_size
            ax.contour(xs, ys, density, levels=[0.5], colors=[lc], linewidths=1.4)   # row 0 is the bottom
        ax.set_xlabel("x (mm)", color=tc, fontsize=9)
        ax.set_ylabel("y (mm)", color=tc, fontsize=9)
        ax.tick_params(colors=tc)
        for spine in ax.spines.values():
            spine.set_edgecolor(tc)
        ax.set_title(title, color=tc, fontsize=10)
        self._fig.tight_layout(pad=1.2)
        self.draw_idle()

    def show_message(self, text):
        """An empty canvas with one centred line, e.g. before there is a result."""
        bg, tc, _ = self._colours()
        self._fig.clf()
        self._fig.patch.set_facecolor(bg)
        self._fig.text(0.5, 0.5, text, ha="center", va="center", color=tc, fontsize=11, wrap=True)
        self._ax_d = self._ax_c = None
        self._im = self._line = None
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


TENSION, COMPRESSION = "#c0392b", "#2e86de"


def draw_network(ax, points, network, ink):
    """Draw bars (width from their area, red in tension and blue in compression) and nodes on `ax`.

    `points` are the node positions in the axes' coordinates, 2 or 3 per node; a node's dot
    grows with the bar area that meets there.  Returns the artists, so they can be removed.
    """
    from matplotlib.collections import LineCollection
    bars = np.asarray(network["bars"], dtype=int).reshape(-1, 2)
    areas = np.asarray(network["areas"], dtype=float)
    if not len(bars) or not np.max(areas) > 0:
        return []
    relative = areas / np.max(areas)
    shown = relative > 1e-2
    forces = network.get("forces")
    if forces is not None:
        forces = np.asarray(forces, dtype=float)
        colours = np.where(forces[shown] >= 0, TENSION, COMPRESSION)
    else:
        colours = ink
    widths = 0.4 + 3.6 * np.sqrt(relative[shown])
    segments = points[bars[shown]]
    if points.shape[1] == 3:
        from mpl_toolkits.mplot3d.art3d import Line3DCollection
        lines = Line3DCollection(segments, colors=colours, linewidths=widths)
        ax.add_collection3d(lines)
    else:
        lines = LineCollection(segments, colors=colours, linewidths=widths, zorder=2)
        ax.add_collection(lines)
    artists = [lines]
    joint = np.zeros(len(points))
    np.add.at(joint, bars[shown, 0], relative[shown])
    np.add.at(joint, bars[shown, 1], relative[shown])
    used = joint > 0
    if used.any():
        sizes = 4 + 30 * joint[used] / joint.max()
        values = network.get("node_values")
        if values is not None and len(values) == len(points):
            # The node's own value (methods/truss.py, "Node value"), on a colour scale.
            colour = {"c": np.asarray(values, dtype=float)[used], "cmap": "viridis"}
        else:
            colour = {"c": ink}
        artists.append(ax.scatter(*points[used].T, s=sizes, zorder=3, linewidths=0, **colour))
    return artists
