# plugins/representations/mmc.py — moving morphable components.
#
# The design is a set of bars, each described by five numbers: its centre
# (xc, yc), its half-length L, its half-thickness t and its angle θ.  A few
# dozen bars give a design of a few hundred variables instead of one per
# element, and every design is a set of straight members by construction —
# the explicit-geometry idea of Guo, Zhang & Zhong (2014).
#
# Each bar is a super-ellipse, described by its topology description function
#
#     φ_i(x, y) = (t/p) · (1 − (x'/L)^p − (y'/t)^p),      p = 6,
#
# in the bar's own axes (x' along it, y' across), positive inside the bar.  The
# factor t/p makes φ_i a length: near the long edges it is the distance to the
# edge.  An element's density from one bar is a smoothed Heaviside of φ_i at
# the element centre, ρ_i = ½ (1 + tanh(φ_i / ε)), with ε a few element widths
# so that every edge is seen by the elements it crosses — a much sharper edge
# leaves the gradient to the few element centres that happen to lie inside it,
# and the optimiser then loses bars between iterations.  The bars are joined
# by a smooth union,
#
#     ρ = 1 − Π_i (1 − ρ_i),
#
# which is 1 inside any bar, 0 outside all of them, and differentiable
# everywhere (a max over bars would not be).  The chain rule back to the five
# numbers of every bar is written out in backward().
#
# Every variable is normalised to [0, 1] — position across the domain, length
# up to half the diagonal, thickness up to `max_thickness` of the shorter
# side, angle over a full turn — so a move limit means the same for each.
#
# The start design is the usual one: a grid of n_x × n_y cells, each holding
# two bars crossing at its centre along its diagonals.
#
# Differences from the reference MMC code (MMC188): the union is the smooth
# product above rather than a maximum of the description functions, the
# Heaviside is a tanh rather than a cubic polynomial and is taken at element
# centres rather than averaged over the nodes, and the bar thickness is
# constant along its length (MMC188 lets it vary linearly).  Each simplifies
# the gradient; none changes what the method is.
#
# Reference: X. Guo, W. Zhang, W. Zhong, "Doing topology optimization
# explicitly and geometrically — a new moving morphable components based
# framework", Journal of Applied Mechanics 81 (2014) 081009.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.representation import Representation

#: Exponent of each bar's super-ellipse: 2 is an ellipse, larger is squarer.
P = 6
#: Variables per bar: centre x, centre y, half-length, half-thickness, angle.
PER_BAR = 5


class MovingMorphableComponents(Representation):
    """Bars described by centre, half-length, half-thickness and angle, projected onto the grid."""

    name = "mmc"
    label = "Moving morphable components"
    order = 20
    element_wise = False
    advice = ("Its variables are positions, lengths and angles across the whole domain, so the "
              "updater's move limit moves bars a long way: about 0.02 (method.move) keeps them on "
              "the load between iterations; the usual 0.2 lets them jump off and back.")
    schedulable = ("edge_width",)    # wide edges early, crisp geometry at the end
    params = (
        Param("n_x", 4, "Cells across", "Start layout: cells across the domain, each with two crossing bars.",
              min=1, max=20),
        Param("n_y", 2, "Cells down", "Start layout: cells down the domain.", min=1, max=20),
        Param("max_thickness", 0.2, "Largest thickness",
              "Largest half-thickness of a bar, as a fraction of the domain's shorter side.",
              min=0.01, max=0.5, step=0.01, decimals=3),
        Param("start_thickness", 0.4, "Start thickness",
              "Half-thickness of the start bars, as a fraction of the largest.",
              min=0.05, max=1.0, step=0.05, decimals=2),
        Param("edge_width", 1.0, "Edge width",
              "Width of each bar's smoothed edge, in element widths: smaller is crisper "
              "but gives the optimiser less of a gradient to follow.",
              min=0.1, max=5.0, step=0.1, decimals=2, units="elements"),
    )

    def __init__(self, n_x=4, n_y=2, max_thickness=0.2, start_thickness=0.4, edge_width=1.0):
        self.n_x, self.n_y = int(n_x), int(n_y)
        self.max_thickness = float(max_thickness)
        self.start_thickness = float(start_thickness)
        self.edge_width = float(edge_width)

    def setup(self, problem):
        self.X, self.Y = problem.elem_x, problem.elem_y
        Lx, Ly = problem.Lx, problem.Ly
        h = min(problem.dx, problem.dy)
        self.h = h
        self.eps = self.edge_width * h
        # Physical value = low + z × span, for the five variables in order.
        self.low = np.array([0.0, 0.0, h, 0.5 * h, -np.pi])
        self.span = np.array([Lx, Ly, 0.5 * np.hypot(Lx, Ly) - h,
                              self.max_thickness * min(Lx, Ly) - 0.5 * h, 2.0 * np.pi])
        self._start = self._start_layout(Lx, Ly)

    def _start_layout(self, Lx, Ly):
        """Two bars crossing along the diagonals of every cell of an n_x × n_y grid."""
        width, height = Lx / self.n_x, Ly / self.n_y
        angle = np.arctan2(height, width)
        bars = []
        for i in range(self.n_x):
            for j in range(self.n_y):
                centre = ((i + 0.5) * width, (j + 0.5) * height)
                for theta in (angle, -angle):
                    bars.append([*centre, 0.5 * np.hypot(width, height),
                                 self.start_thickness * (self.low[3] + self.span[3]), theta])
        return np.clip((np.array(bars) - self.low) / self.span, 0.0, 1.0).reshape(-1)

    def set_parameter(self, name, value):
        self.edge_width = float(value)
        self.eps = self.edge_width * self.h

    @property
    def n_bars(self):
        return self._start.size // PER_BAR

    def initial(self):
        return self._start.copy()

    def bounds(self):
        return np.zeros_like(self._start), np.ones_like(self._start)

    # ── The projection ────────────────────────────────────────────────────────

    def _bars(self, z):
        """Every bar's description function and its parts, on the element grid: arrays (n_bars, nely, nelx)."""
        xc, yc, L, t, theta = (column[:, None, None] for column in (self.low + z.reshape(-1, PER_BAR) * self.span).T)
        dx, dy = self.X[None] - xc, self.Y[None] - yc
        c, s = np.cos(theta), np.sin(theta)
        along, across = c * dx + s * dy, -s * dx + c * dy
        a, b = along / L, across / t
        shape = 1.0 - a ** P - b ** P          # the dimensionless description function
        tanh = np.tanh(t / P * shape / self.eps)
        return {"L": L, "t": t, "c": c, "s": s, "along": along, "across": across,
                "a": a, "b": b, "shape": shape, "tanh": tanh, "rho": 0.5 * (1.0 + tanh)}

    def density(self, z):
        bars = self._bars(z)
        return 1.0 - np.prod(1.0 - bars["rho"], axis=0)

    def backward(self, z, sensitivity):
        bars = self._bars(z)
        outside = 1.0 - bars["rho"]
        # dρ/dρ_i = Π_{j≠i} (1 − ρ_j): the product over every other bar, from
        # running products in both directions (no division by 1 − ρ_i).
        before = np.concatenate([np.ones_like(outside[:1]), np.cumprod(outside, axis=0)[:-1]])
        after = np.concatenate([np.cumprod(outside[::-1], axis=0)[::-1][1:], np.ones_like(outside[:1])])
        # d(objective)/dφ_i per element.
        g = sensitivity[None] * before * after * 0.5 / self.eps * (1.0 - bars["tanh"] ** 2)

        a, b, L, t = bars["a"], bars["b"], bars["L"], bars["t"]
        # φ = (t/P)·shape: every derivative of `shape` is scaled by t/P, and the
        # thickness also appears in the factor itself.
        dphi_dalong = -t * a ** (P - 1) / L
        dphi_dacross = -b ** (P - 1)
        c, s = bars["c"], bars["s"]
        per_bar = np.stack([
            np.sum(g * (-c * dphi_dalong + s * dphi_dacross), axis=(1, 2)),                 # centre x
            np.sum(g * (-s * dphi_dalong - c * dphi_dacross), axis=(1, 2)),                 # centre y
            np.sum(g * t * a ** P / L, axis=(1, 2)),                                        # half-length
            np.sum(g * (b ** P + bars["shape"] / P), axis=(1, 2)),                          # half-thickness
            np.sum(g * (dphi_dalong * bars["across"] - dphi_dacross * bars["along"]), axis=(1, 2)),  # angle
        ], axis=1)
        return (per_bar * self.span).reshape(-1)       # d/dz = d/d(physical) × span
