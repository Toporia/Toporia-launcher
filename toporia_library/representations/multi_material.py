# plugins/representations/multi_material.py — a density and candidate-material weights per element.
#
# Several fields per element (Wave 5).  Every element carries its density ρ_e (topology:
# material or void) and one weight x_{m,e} ∈ [0, 1] per candidate material m:
#
#     z = [ρ ; x_1 ; … ; x_M]      shape (1 + M, nely, nelx)  (or the 3-D element shape)
#
# The density goes through the filters to the physics like any density; the weights are
# the field "material", read by a multi-material law (plugins/interpolations/dmo.py) that
# turns them into a stiffness and a mass per element.  The chain rule back is the identity
# on each part:  dz = [dρ ; dx_1 ; … ; dx_M].
#
# Use a general-gradient updater (MMA): optimality criteria assume one density per element.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.representation import Representation


class MultiMaterial(Representation):
    """A density plus one weight per candidate material on every element (DMO's design variables)."""

    name = "multi_material"
    label = "Density and material choice (multi-material)"
    use_when = ("To choose, element by element, between void and two or three materials of different stiffness "
                "and weight; pair with the DMO material law and MMA.")
    reference = ("Discrete material optimisation variables: J. Stegmann, E. Lund, \"Discrete material optimization of"
                 " general composite shell structures\", Int. J. Numer. Meth. Engng 62 (2005) 2009-2027."
                 " Papers: https://doi.org/10.1002/nme.1259")
    order = 60
    dims = None
    fields = ("material",)
    check_with = {"interpolation": {"type": "dmo"}}
    advice = "Use MMA (a general-gradient updater) with a move limit near 0.1."
    params = (
        Param("materials", 2, "Candidate materials", "How many materials every element chooses between "
              "(besides void). The material law sets their stiffness and weight.", min=2, max=3),
        Param("start_weight", 0.5, "Start weight", "The first value of every material weight.",
              min=0.0, max=1.0, step=0.05, decimals=3),
    )

    def __init__(self, materials=2, start_weight=0.5):
        self.materials, self.start_weight = int(materials), float(start_weight)

    def setup(self, problem):
        self.problem = problem
        self.shape = tuple(problem.shape)

    def initial(self):
        problem = self.problem
        density = np.clip(np.full(self.shape, problem.scenario.volfrac), problem.lower_bound, problem.upper_bound)
        return np.concatenate([density[None], np.full((self.materials,) + self.shape, self.start_weight)])

    def bounds(self):
        problem = self.problem
        low = np.concatenate([problem.lower_bound[None], np.zeros((self.materials,) + self.shape)])
        high = np.concatenate([problem.upper_bound[None], np.ones((self.materials,) + self.shape)])
        return low, high

    def density(self, z):
        return z[0]

    def backward(self, z, sensitivity):
        out = np.zeros_like(z, dtype=float)
        out[0] = sensitivity
        return out

    def extra(self, z):
        return {"material": z[1:]}

    def backward_extra(self, z, sensitivities):
        out = np.zeros_like(z, dtype=float)
        out[1:] = sensitivities["material"]
        return out
