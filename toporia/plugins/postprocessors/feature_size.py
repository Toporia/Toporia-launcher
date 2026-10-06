# plugins/postprocessors/feature_size.py — the thinnest member and the smallest hole.
#
# Length-scale control is what filters, projections and the robust formulation
# promise; this measures what was delivered.  For every solid element of the
# black-and-white design, the distance to the nearest void element is taken
# (Euclidean, in elements, centre to centre).  Along the middle of a member
# that distance has a ridge, and the member is about 2d - 1 elements wide
# where the ridge height is d; the thinnest member is the lowest ridge.
# Ridges are the elements whose distance is at least that of all eight
# neighbours, so the corners of a stepped diagonal edge, whose inner
# neighbours lie deeper, do not count as thin members.  Holes are measured
# the same way on the void, with the outside of the domain counted as solid
# so the domain edge is not a hole.  Only free elements count: a prescribed
# hole or solid ring is not the design's doing.  The answer is good to about
# one element; None means there is no member (or hole) at all.

import numpy as np
from scipy import ndimage

from toporia.framework.parts.postprocess import PostProcessor

from ._measure import pinned


def thinnest(field, free):
    """Width, in elements, of the thinnest part of `field` (bool), from its distance ridge; None if empty."""
    distance = ndimage.distance_transform_edt(field)
    ridge = field & free & (distance >= ndimage.maximum_filter(distance, size=3))
    if not ridge.any():
        return None
    return float(2.0 * distance[ridge].min() - 1.0)


class FeatureSize(PostProcessor):
    """The thinnest solid member and the smallest hole, from the distance to the other phase."""

    name = "feature_size"
    label = "Feature size"
    order = 30
    table_metrics = ("min_member_mm", "min_hole_mm")

    def process(self, result):
        problem = result.problem
        solid = result.solid()
        free = ~pinned(problem)
        size = min(problem.dx, problem.dy)
        member = thinnest(np.pad(solid, 1, constant_values=False), np.pad(free, 1))
        hole = thinnest(np.pad(~solid, 1, constant_values=False), np.pad(free, 1))
        return {"min_member_mm": None if member is None else member * size,
                "min_hole_mm": None if hole is None else hole * size}
