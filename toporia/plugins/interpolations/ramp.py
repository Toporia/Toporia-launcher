# plugins/interpolations/ramp.py — Rational Approximation of Material Properties.
#
#     E(ρ) = Emin + ρ / (1 + q(1 − ρ)) · (E0 − Emin)
#     dE/dρ = (1 + q) / (1 + q(1 − ρ))² · (E0 − Emin)
#
# Like SIMP it penalises grey material (more strongly as q grows), but its
# slope at ρ = 0 is finite and non-zero, (E0 − Emin)/(1 + q), where SIMP's is
# zero.  That matters for design-dependent loads (pressure, self-weight),
# where a void element must still feel a sensitivity.  The authors also show
# that for q large enough the minimum-compliance problem is concave in ρ, so
# its optimum is black and white.  q = 8 behaves roughly like SIMP p = 3.
#
# Reference: M. Stolpe, K. Svanberg, "An alternative interpolation scheme for
# minimum compliance topology optimization", Structural and Multidisciplinary
# Optimization 22 (2001) 116–124.

from toporia.framework.params import Param
from toporia.framework.parts.interpolation import Interpolation


class RAMP(Interpolation):
    """E = Emin + ρ / (1 + q(1 − ρ)) (E0 − Emin): a rational law with a non-zero slope at void."""

    name = "ramp"
    label = "RAMP (rational)"
    order = 20
    schedulable = ("q",)
    params = (
        Param("q", 8.0, "RAMP q",
              "Penalisation of grey material. 0 is linear (no penalty); about 8 behaves like "
              "SIMP p = 3 for compliance.",
              min=0.0, max=100.0, step=1.0, decimals=2),
    )

    def __init__(self, q=8.0):
        self.q = float(q)

    def stiffness(self, density, E0, Emin):
        return Emin + density / (1.0 + self.q * (1.0 - density)) * (E0 - Emin)

    def slope(self, density, E0, Emin):
        return (1.0 + self.q) / (1.0 + self.q * (1.0 - density)) ** 2 * (E0 - Emin)
