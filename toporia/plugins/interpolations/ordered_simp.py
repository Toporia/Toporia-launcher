# plugins/interpolations/ordered_simp.py — ordered SIMP: several materials, one variable per element.
#
# The materials are ordered by density, ρ_1 = 0 (void) < ρ_2 < … < ρ_m = 1 (the
# solid), each with a Young's modulus (as a fraction of E0) f_1 = 0 < … < f_m = 1.
# One design variable ρ per element runs through them all; between neighbouring
# materials i and i+1 a SIMP power law is used,
#
#     t = (ρ − ρ_i) / (ρ_{i+1} − ρ_i),     E(ρ) = Emin + [f_i + t^p (f_{i+1} − f_i)] (E0 − Emin)
#     dE/dρ = p t^(p−1) (f_{i+1} − f_i) / (ρ_{i+1} − ρ_i) · (E0 − Emin)
#
# For p > 1 the stiffness is flat just above each material's density, so the
# optimiser is driven to sit exactly on one of the m materials instead of in
# between.  With m = 2 the law is plain SIMP.
#
# It fits the Interpolation interface (stiffness and slope per element).  What
# it does NOT contain is the cost side of the paper: Zuo & Saitou also give each
# material a cost and constrain the interpolated cost instead of the volume.
# Toporia's volume response is ρ itself (mass fraction of the solid), so here the
# constraint is on Σρ, which is the mass if every material's density equals its
# ρ_i as given.  Constraining another per-material cost would need the volume
# response to accept an interpolation (a framework change); it is not done.
#
# Reference: W. Zuo, K. Saitou, "Multi-material topology optimization using
# ordered SIMP interpolation", Structural and Multidisciplinary Optimization 55
# (2017) 477–491, doi:10.1007/s00158-016-1513-3.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.interpolation import Interpolation
from toporia.plugins.shared_params import PENAL


class OrderedSIMP(Interpolation):
    """Piecewise SIMP between an ordered list of materials (void, up to two grey ones, solid)."""

    name = "ordered_simp"
    label = "Ordered SIMP (multi-material)"
    order = 30
    schedulable = ("penal",)
    params = (
        Param("n_materials", 4, "Materials",
              "How many materials the variable runs through, void and solid included "
              "(2 = plain SIMP, 3 uses material 2, 4 uses materials 2 and 3).",
              min=2, max=4, step=1),
        PENAL,
        Param("rho2", 0.4, "Density of material 2",
              "Normalised density at which the second material sits (must lie between void and the next material).",
              min=0.01, max=0.98, step=0.05, decimals=2),
        Param("E2", 0.25, "Modulus of material 2",
              "Young's modulus of material 2 as a fraction of the solid's E0.",
              min=0.0, max=1.0, step=0.05, decimals=2),
        Param("rho3", 0.7, "Density of material 3",
              "Normalised density of the third material (used when Materials = 4).",
              min=0.02, max=0.99, step=0.05, decimals=2),
        Param("E3", 0.55, "Modulus of material 3",
              "Young's modulus of material 3 as a fraction of E0 (used when Materials = 4).",
              min=0.0, max=1.0, step=0.05, decimals=2),
    )

    def __init__(self, n_materials=4, penal=3.0, rho2=0.4, E2=0.25, rho3=0.7, E3=0.55):
        self.penal = float(penal)
        n = int(round(n_materials))
        grey = [(float(rho2), float(E2)), (float(rho3), float(E3))][: max(n - 2, 0)]
        self.rho = np.array([0.0] + [r for r, _ in grey] + [1.0])
        self.frac = np.array([0.0] + [e for _, e in grey] + [1.0])
        # Strictly ordered materials, or the segments below would divide by zero or fold back.
        if np.any(np.diff(self.rho) <= 0.0) or np.any(np.diff(self.frac) < 0.0):
            raise ValueError("ordered_simp: densities must strictly increase and moduli must not "
                             f"decrease along void < material 2 < material 3 < solid (got densities "
                             f"{self.rho.tolist()}, moduli {self.frac.tolist()})")

    def _segment(self, density):
        """Index i of the segment [ρ_i, ρ_{i+1}] each density falls in, and t within it."""
        rho = np.clip(density, 0.0, 1.0)
        i = np.clip(np.searchsorted(self.rho, rho, side="right") - 1, 0, len(self.rho) - 2)
        width = self.rho[i + 1] - self.rho[i]
        return i, (rho - self.rho[i]) / width, width

    def stiffness(self, density, E0, Emin):
        i, t, _ = self._segment(density)
        f = self.frac[i] + t ** self.penal * (self.frac[i + 1] - self.frac[i])
        return Emin + f * (E0 - Emin)

    def slope(self, density, E0, Emin):
        i, t, width = self._segment(density)
        return self.penal * t ** (self.penal - 1.0) * (self.frac[i + 1] - self.frac[i]) / width * (E0 - Emin)
