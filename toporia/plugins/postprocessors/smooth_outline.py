# plugins/postprocessors/smooth_outline.py — the outline fitted with smooth curves.
#
# The contour of an element field is piecewise linear and follows the grid, so
# a diagonal member has stair-step wiggles that a cutter or a CAD user then has
# to live with.  Geometric post-processing replaces it with a smooth curve
# through the same shape (review: Subedi et al., J. Comput. Inf. Sci. Eng. 20
# (2020)).  Here every closed loop of the contour of the density, at the level
# the black-and-white design was cut at (the same contour export_svg writes,
# _measure.outlines), is smoothed in one of two ways:
#
#   spline    a periodic smoothing spline (scipy splprep, per = 1) that may
#             move each point by about `tolerance` element sizes, sampled
#             densely; the result is C2 smooth.
#   chaikin   corner cutting, repeated: each pass replaces every corner by two
#             points a quarter of the way along its edges.  Converges to a
#             quadratic B-spline and never leaves the original polygon.
#
# Smoothing can pull a point across the domain edge, so points are clipped
# back to it.  The curves are written as design_smooth.svg and design_smooth.dxf
# with the writers of the plain exporters (svg_text, dxf_text): polylines of
# many short segments, in mm.  2-D only: a 3-D design has a surface, which
# needs a mesh smoother rather than a curve fit.

import numpy as np
from scipy.interpolate import splev, splprep

from toporia.framework.params import Param
from toporia.framework.parts.postprocess import PostProcessor

from ._measure import element_size, outlines
from .export_dxf import dxf_text
from .export_svg import svg_text


def chaikin(polygon, passes):
    """A closed polygon (first point repeated) with its corners cut `passes` times."""
    points = np.asarray(polygon, dtype=float)[:-1]
    for _ in range(passes):
        following = np.roll(points, -1, axis=0)
        cut = np.empty((2 * len(points), 2))
        cut[0::2] = 0.75 * points + 0.25 * following
        cut[1::2] = 0.25 * points + 0.75 * following
        points = cut
    return np.vstack([points, points[:1]])


def spline(polygon, tolerance, per_segment):
    """A closed polygon replaced by a periodic smoothing spline, sampled `per_segment` times per input segment.

    `tolerance` is the length (mm) a point may be moved: splprep's s is the
    summed squared distance, so s = n tolerance².  Loops too short to fit are returned unchanged.
    """
    points = np.asarray(polygon, dtype=float)
    keep = np.r_[True, np.any(np.diff(points, axis=0) != 0.0, axis=1)]      # drop repeated points
    points = points[keep]
    if len(points) < 6:
        return np.asarray(polygon, dtype=float).copy()
    tck, _ = splprep([points[:, 0], points[:, 1]], s=len(points) * tolerance ** 2, per=1)
    x, y = splev(np.linspace(0.0, 1.0, per_segment * len(points) + 1), tck)
    curve = np.column_stack([x, y])
    curve[-1] = curve[0]                                                      # exactly closed
    return curve


def smoothed(result, method, tolerance, passes):
    """The smoothed closed loops [(n, 2) arrays, in mm, y up] of the design's contour."""
    problem = result.problem
    h = element_size(problem)
    loops = []
    for loop in outlines(result):
        curve = chaikin(loop, passes) if method == "chaikin" else spline(loop, tolerance * h, 4)
        curve[:, 0] = np.clip(curve[:, 0], 0.0, problem.Lx)
        curve[:, 1] = np.clip(curve[:, 1], 0.0, problem.Ly)
        curve[-1] = curve[0]
        loops.append(curve)
    return loops


class SmoothOutline(PostProcessor):
    """The contour of the design fitted with smooth curves, as SVG and DXF in millimetres."""

    name = "smooth_outline"
    reference = (
        'Smoothing of extracted outlines as reviewed in Subedi et al., J. Comput. Inf. Sci. '
        'Eng. (2020); periodic smoothing splines (SciPy splprep) or Chaikin corner cutting '
        '(Chaikin 1974).'
        ' Papers: https://doi.org/10.1115/1.4047429 https://doi.org/10.1016/0146-664X%2874%2990028-8'
    )
    label = "Smooth outline (SVG + DXF)"
    use_when = "When the jagged element outline should become smooth curves for CAD or cutting."
    order = 55
    table_metrics = ()          # files, not numbers to compare
    params = (
        Param("method", "spline", "Smoothing",
              "Spline: a periodic smoothing spline through each loop. Chaikin: repeated corner cutting.",
              choices=(("spline", "Smoothing spline"), ("chaikin", "Chaikin corner cutting"))),
        Param("tolerance", 0.5, "Spline tolerance",
              "How far, in element sizes, the spline may move the contour. Larger is smoother.",
              min=0.0, max=3.0, step=0.1, decimals=2),
        Param("passes", 3, "Chaikin passes", "How many times corners are cut (Chaikin only).", min=1, max=6),
    )

    def __init__(self, method="spline", tolerance=0.5, passes=3):
        self.method, self.tolerance, self.passes = method, float(tolerance), int(passes)

    def process(self, result):
        problem = result.problem
        if getattr(problem, "dims", 2) == 3:
            raise ValueError("smooth outlines are 2-D only: a 3-D design has a surface, not an outline")
        loops = smoothed(result, self.method, self.tolerance, self.passes)
        result.file("design_smooth.svg").write_text(
            svg_text(loops, problem.Lx, problem.Ly, "evenodd"), encoding="utf-8")
        result.file("design_smooth.dxf").write_text(dxf_text(loops), encoding="ascii")
        return {"outlines": len(loops), "points": int(sum(len(loop) - 1 for loop in loops))}
