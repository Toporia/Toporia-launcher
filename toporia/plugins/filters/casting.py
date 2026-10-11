# plugins/filters/casting.py - CastingFilter (no undercuts along a draw direction)
#
# A cast part can be pulled out of a one-piece mould along the draw direction
# only if, on every line parallel to it, the material is one solid run that
# starts at the parting plane.  In density terms the filtered density may only
# decrease as one moves along the draw direction, away from the parting plane:
#
#     rho_0 = x_0                                        (the element on the parting plane)
#     rho_k = smin(x_k, rho_{k-1})                       k = 1, 2, ...  along the draw direction
#     smin(a, b) = 0.5 (a + b - sqrt((a - b)^2 + eps) + sqrt(eps))
#
# i.e. the running minimum of the design, smoothed.  rho_k <= rho_{k-1} +
# sqrt(eps)/2, so the output is monotone up to 5e-4 (eps = 1e-6); the smoothing
# makes the running minimum differentiable, and backward() is its exact
# adjoint, found by one reverse sweep:
#
#     d smin / d a = 0.5 (1 - d/s),   d smin / d b = 0.5 (1 + d/s),   d = a - b,  s = sqrt(d^2 + eps)
#     g_x[k] = g_rho[k] * dsmin/da,   g_rho[k-1] += g_rho[k] * dsmin/db      (k from the end back to 1)
#
# The recursion and smoothing are the same device as the AM overhang filter
# (am.py, Langelaar 2016) with the supporting neighbourhood reduced to the one
# element behind; this is the "cumulative smooth minimum" form of the explicit
# casting parameterisation, not the projection form of Xia et al.
#
# Direction "+y" means the mould is drawn off toward +y, so the parting plane is
# the low-y face and density decreases with increasing y; "-y" is the opposite.
# Likewise x, and z in 3-D.  Rows are numbered from the bottom of the image
# (row 0 = lowest y), as in am.py.
#
# Passive / void elements are not treated specially (as in symmetry.py): the
# model re-imposes them on the physical density afterwards.
#
# References: Gersborg & Andreasen, "An explicit parameterization for casting
# constraints in gradient driven topology optimization", SMO 44 (2011) 875-881;
# Xia, Shi, Wang & Liu, "Topology optimization for the casting constraints",
# CMAME 199 (2010) (the level-set formulation); Guest & Zhu 2012.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter

AXES = {"x": -1, "y": -2, "z": 0}   # array axis of each coordinate (see extrusion.py)


class CastingFilter(Filter):
    """No undercuts along a draw direction: density can only decrease along it (smooth running minimum).

    direction : "+x", "-x", "+y", "-y", "+z" or "-z" (z only in 3-D).
    """

    _EPS = 1e-6     # smoothing of the min; sets the monotonicity tolerance sqrt(eps)/2

    name = "casting"
    label = "Casting (no undercuts)"
    order = 90
    dims = (2, 3)
    params = (
        Param("direction", "+y", "Draw direction",
              "The mould is drawn off in this direction; material must be one solid run from the parting plane on the opposite face.",
              choices=(("+x", "+x"), ("-x", "-x"), ("+y", "+y"), ("-y", "-y"), ("+z", "+z (3-D only)"), ("-z", "-z (3-D only)"))),
    )

    def __init__(self, direction="+y"):
        key = str(direction).strip().lower()
        if len(key) == 1:
            key = "+" + key
        if len(key) != 2 or key[0] not in "+-" or key[1] not in AXES:
            raise ValueError(f"direction must be one of +x, -x, +y, -y, +z, -z - got {direction!r}")
        self.direction = key

    def setup(self, problem, solver):
        if self.direction[1] == "z" and getattr(problem, "dims", 2) != 3:
            raise ValueError("a draw direction along z needs a 3-D problem; use x or y in 2-D")

    def _lines(self, x):
        # The field with the draw axis first and the parting plane at index 0.
        lines = np.moveaxis(x, AXES[self.direction[1]], 0)
        return lines if self.direction[0] == "+" else lines[::-1]

    def _restore(self, lines, like):
        if self.direction[0] == "-":
            lines = lines[::-1]
        return np.ascontiguousarray(np.moveaxis(lines, 0, AXES[self.direction[1]])).reshape(like.shape)

    def _smin(self, a, b):
        s = np.sqrt((a - b) ** 2 + self._EPS)
        return 0.5 * ((a + b) - s + np.sqrt(self._EPS))

    def _sweep(self, lines):
        rho = np.empty(lines.shape)
        rho[0] = lines[0]
        for k in range(1, len(lines)):
            rho[k] = self._smin(lines[k], rho[k - 1])
        return rho

    def forward(self, x):
        return self._restore(self._sweep(self._lines(x)), x)

    def backward(self, x_in, sensitivity):
        lines = self._lines(x_in)
        rho = self._sweep(lines)            # recomputed rather than stored: cheap, and keeps no state
        g_rho = np.array(self._lines(sensitivity), dtype=float)
        g_x = np.empty(lines.shape)
        for k in range(len(lines) - 1, 0, -1):
            d = lines[k] - rho[k - 1]
            s = np.sqrt(d * d + self._EPS)
            g_x[k] = g_rho[k] * 0.5 * (1.0 - d / s)
            g_rho[k - 1] += g_rho[k] * 0.5 * (1.0 + d / s)
        g_x[0] = g_rho[0]
        return self._restore(g_x, x_in)
