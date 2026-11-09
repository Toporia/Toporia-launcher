# toporia_library/representations/element_density.py — one density per element.
#
# The classic representation (Bendsøe 1989; Sigmund's 99-line code): the design
# variables ARE the element densities, so density() and backward() are the
# identity.  Elements in holes and solid rings have equal lower and upper
# bounds, so they cannot move.
#
# The start design is the volume fraction everywhere (the usual choice, which
# meets the budget from the first iteration) or a full domain (what BESO and
# volume minimisation under a stress limit start from).
#
#
# The map is the identity: x = z, so backward(z, s) = s, the bounds are the problem's
# per-element bounds (0 in holes, 1 in forced-solid rings), and the start is uniform at
# the volume fraction (clipped to the bounds) or full.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.representation import Representation


class ElementDensity(Representation):
    """The design variables are the element densities."""

    name = "element_density"
    label = "Element densities"
    use_when = "The default: one variable per element. Works with every updater, filter and model."
    reference = (
        'One density per element: M. P. Bendsoe, Structural Optimization 1 (1989) 193-202;'
        " Sigmund's 99-line code (2001)."
        ' Papers: https://doi.org/10.1007/BF01650949 https://doi.org/10.1007/s001580050176'
    )
    order = 10
    element_wise = True
    dims = (2, 3)
    params = (
        Param("start", "uniform", "Start design",
              "Uniform at the volume fraction (meets the budget at once), a full domain "
              "(what BESO and volume minimisation under a stress limit start from), or a hole in "
              "the middle (unit cells: a uniform cell has no pattern to grow from).",
              choices=(("uniform", "Uniform at the volume fraction"), ("full", "Full domain"),
                       ("hole", "A hole in the middle (unit cells)"))),
    )

    def __init__(self, start="uniform"):
        self.start = start

    def setup(self, problem):
        self.problem = problem

    def initial(self):
        problem = self.problem
        if self.start == "hole":
            return self._with_hole()
        value = problem.scenario.volfrac if self.start == "uniform" else 1.0
        return np.clip(np.full(problem.shape, value), problem.lower_bound, problem.upper_bound)

    def _with_hole(self):
        """Void in a disc (ball in 3-D) of a quarter of the smallest side around the centre, the rest
        uniform so the total meets the volume fraction (as the unit-cell codes of Xia & Breitkopf start)."""
        problem = self.problem
        centres = [problem.elem_x, problem.elem_y] + ([problem.elem_z] if problem.dims == 3 else [])
        middle = [problem.Lx / 2, problem.Ly / 2] + ([problem.Lz / 2] if problem.dims == 3 else [])
        radius = 0.25 * min([problem.Lx, problem.Ly] + ([problem.Lz] if problem.dims == 3 else []))
        inside = sum((c - m) ** 2 for c, m in zip(centres, middle, strict=True)) <= radius ** 2
        outside = min(1.0, problem.scenario.volfrac * inside.size / max(int((~inside).sum()), 1))
        return np.clip(np.where(inside, 0.0, outside), problem.lower_bound, problem.upper_bound)

    def bounds(self):
        return self.problem.lower_bound, self.problem.upper_bound

    def density(self, z):
        return z

    def backward(self, z, sensitivity):
        return sensitivity
