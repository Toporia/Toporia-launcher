# plugins/representations/fibre_angle.py — a density and a fibre angle per element.
#
# Several fields per element (Wave 5).  Every element carries its density ρ_e and the
# direction θ_e of its fibres (radians from +x):
#
#     z = [ρ ; θ]      shape (2, nely, nelx)
#
# The density goes through the filters to the physics; the angle is the field "angle",
# read by an orthotropic physics (plugins/physics/q4_orthotropic.py), which turns it into
# the element's rotated stiffness.  Continuous fibre-angle optimisation of this kind has
# many local optima (θ and θ + π are the same fibre); the start angle matters, and a
# small move limit helps.  The angle is bounded to [−π, π] so it can turn freely through
# the half turn either way.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.representation import Representation


class FibreAngle(Representation):
    """A density plus a fibre direction on every element (continuous fibre-angle optimisation)."""

    name = "fibre_angle"
    label = "Density and fibre angle"
    use_when = "With the fibre-reinforced physics: lay out material and steer its fibres along the load paths."
    reference = ("Continuous fibre-angle optimisation: J. Stegmann, E. Lund, Int. J. Numer. Meth. Engng 62 (2005)"
                 " 2009-2027; T. Nomura et al., Int. J. Numer. Meth. Engng 101 (2015) 571-605."
                 " Papers: https://doi.org/10.1002/nme.1259 https://doi.org/10.1002/nme.4799")
    order = 61
    fields = ("angle",)
    check_with = {"method": "q4_orthotropic+mma"}
    advice = "Use MMA with a move limit near 0.1; the start angle steers which local optimum is found."
    params = (
        Param("start_angle", 0.0, "Start angle", "The fibres' first direction, in degrees from +x.",
              min=-180.0, max=180.0, step=15.0, decimals=1, units="deg"),
    )

    def __init__(self, start_angle=0.0):
        self.start_angle = float(start_angle)

    def setup(self, problem):
        self.problem = problem
        self.shape = tuple(problem.shape)

    def initial(self):
        problem = self.problem
        density = np.clip(np.full(self.shape, problem.scenario.volfrac), problem.lower_bound, problem.upper_bound)
        return np.stack([density, np.full(self.shape, np.deg2rad(self.start_angle))])

    def bounds(self):
        problem = self.problem
        return (np.stack([problem.lower_bound, np.full(self.shape, -np.pi)]),
                np.stack([problem.upper_bound, np.full(self.shape, np.pi)]))

    def density(self, z):
        return z[0]

    def backward(self, z, sensitivity):
        out = np.zeros_like(z, dtype=float)
        out[0] = sensitivity
        return out

    def extra(self, z):
        return {"angle": z[1]}

    def backward_extra(self, z, sensitivities):
        out = np.zeros_like(z, dtype=float)
        out[1] = sensitivities["angle"]
        return out
