# plugins/interpolations/simp.py — Solid Isotropic Material with Penalisation.
#
#     E(ρ) = Emin + ρ^p · (E0 − Emin),      dE/dρ = p · (E0 − Emin) · ρ^(p − 1)
#
# With p > 1 an intermediate density gives less stiffness than its share of
# material, so grey is not worth its cost and the optimum is driven towards
# black and white; p = 3 is the usual choice.  The small Emin keeps the
# stiffness matrix non-singular where the design is void.
#
# Reference: M. P. Bendsøe, "Optimal shape design as a material distribution
# problem", Structural Optimization 1 (1989) 193–202.

from toporia.framework.parts.interpolation import Interpolation
from toporia.plugins.shared_params import PENAL


class SIMP(Interpolation):
    """E = Emin + ρ^p (E0 − Emin): the classic power law."""

    name = "simp"
    label = "SIMP (power law)"
    order = 10
    params = (PENAL,)
    schedulable = ("penal",)    # continuation p = 1 -> 3 is common practice

    def __init__(self, penal=3.0):
        self.penal = float(penal)

    # The expressions are written exactly as the Q4 engine wrote them before
    # the law became a part, so results are bit-for-bit the same.
    def stiffness(self, density, E0, Emin):
        return Emin + density ** self.penal * (E0 - Emin)

    def slope(self, density, E0, Emin):
        return self.penal * (E0 - Emin) * density ** (self.penal - 1.0)
