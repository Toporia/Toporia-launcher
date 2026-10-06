# plugins/representations/element_density.py — one density per element.
#
# The classic representation (Bendsøe 1989; Sigmund's 99-line code): the design
# variables ARE the element densities, so density() and backward() are the
# identity.  Elements in holes and solid rings have equal lower and upper
# bounds, so they cannot move.
#
# The start design is the volume fraction everywhere (the usual choice, which
# meets the budget from the first iteration) or a full domain (what BESO and
# volume minimisation under a stress limit start from).

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.representation import Representation


class ElementDensity(Representation):
    """The design variables are the element densities."""

    name = "element_density"
    label = "Element densities"
    order = 10
    element_wise = True
    params = (
        Param("start", "uniform", "Start design",
              "Uniform at the volume fraction (meets the budget at once), or a full domain "
              "(what BESO and volume minimisation under a stress limit start from).",
              choices=(("uniform", "Uniform at the volume fraction"), ("full", "Full domain"))),
    )

    def __init__(self, start="uniform"):
        self.start = start

    def setup(self, problem):
        self.problem = problem

    def initial(self):
        problem = self.problem
        value = problem.scenario.volfrac if self.start == "uniform" else 1.0
        return np.clip(np.full((problem.nely, problem.nelx), value), problem.lower_bound, problem.upper_bound)

    def bounds(self):
        return self.problem.lower_bound, self.problem.upper_bound

    def density(self, z):
        return z

    def backward(self, z, sensitivity):
        return sensitivity
