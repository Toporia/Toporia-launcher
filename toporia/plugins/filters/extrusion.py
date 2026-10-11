# plugins/filters/extrusion.py - ExtrusionFilter (density constant along one axis)
#
# Makes the design a prismatic extrusion: every line of elements parallel to
# the chosen axis carries one density, the line's mean.  It is the same kind of
# linear operator as symmetry.py (an average over a set of elements, broadcast
# back), which is why it is a filter and not a constraint.
#
#     forward:   x_phys = broadcast( mean_axis(x) )          P = (1/n) 1 1^T along the axis
#     backward:  dx     = broadcast( mean_axis(s) )          P is symmetric, so P^T = P
#
# 3-D: constant along x, y or z gives a part of constant cross-section (a
# profile that can be extruded or rolled).  2-D: "constant along x" means a
# design made of full-length horizontal strips (and "y" of full-height columns)
# - rarely a good structure, but it is the 2-D cross-section of the 3-D idea and
# useful as a teaching case.
#
# Passive / void elements are not treated specially: like symmetry.py this acts
# on the design variables, and the model re-imposes passive and void regions on
# the physical density afterwards.
#
# Reference: Ishii & Aomura, "Topology optimization for the extruded three
# dimensional structure with constant cross section", JSME Int. J. Series A 47
# (2004) 198-206.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter

# Array axis of each coordinate; shapes are (nely, nelx) or (nelz, nely, nelx),
# so x and y are the last two axes in both and z is the first axis in 3-D.
AXES = {"x": -1, "y": -2, "z": 0}


class ExtrusionFilter(Filter):
    """Density constant along one axis (average along it, broadcast back).

    axis : "x", "y" or "z" (z only in 3-D) - the direction the profile is extruded along.
    """

    name = "extrusion"
    label = "Extrusion (constant cross-section)"
    order = 70
    dims = (2, 3)
    params = (
        Param("axis", "y", "Axis",
              "The design is constant along this axis (a constant cross-section). In 2-D x gives full-length strips, y full-height columns.",
              choices=(("x", "x"), ("y", "y"), ("z", "z (3-D only)"))),
    )

    def __init__(self, axis="y"):
        key = str(axis).strip().lower()
        if key not in AXES:
            raise ValueError(f"axis must be 'x', 'y' or 'z' - got {axis!r}")
        self.axis = key

    def setup(self, problem, solver):
        if self.axis == "z" and getattr(problem, "dims", 2) != 3:
            raise ValueError("extrusion along z needs a 3-D problem; use axis x or y in 2-D")

    def forward(self, x):
        return np.broadcast_to(x.mean(axis=AXES[self.axis], keepdims=True), x.shape).copy()

    def backward(self, x_in, sensitivity):
        # The averaging projector is symmetric, so the adjoint is the same operation.
        return self.forward(sensitivity)
