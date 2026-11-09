# toporia_library/interpolations/dmo.py — discrete material optimisation: void or one of several materials.
#
# Several fields per element (Wave 5).  The representation multi_material gives every
# element a density ρ and one weight x_m ∈ [0, 1] per candidate material m = 1 … M.  The
# DMO weighting of Stegmann & Lund (2005, their "DMO4" scheme) makes one weight win:
#
#     w_m = x_m^q · Π_{n≠m} (1 − x_n^q)
#
# A material counts fully only when its weight is 1 and every other weight is 0, so
# mixtures are penalised by q (as SIMP penalises grey by p).  The element's stiffness and
# mass are then
#
#     E(ρ, x) = Emin + ρ^p · s(x) · (E0 − Emin),     s(x) = Σ_m w_m e_m
#     mass    = ρ · c(x),                             c(x) = Σ_m w_m c_m
#
# with e_m the stiffness and c_m the mass of material m relative to E0 and to the base
# material.  The volume budget then bounds the mass: a stiff, heavy material costs more of
# it than a soft, light one.  The slopes the sensitivities need:
#
#     ∂E/∂ρ   = p ρ^{p−1} s (E0 − Emin)              ∂mass/∂ρ = c
#     ∂E/∂x_m = ρ^p (E0 − Emin) Σ_k e_k ∂w_k/∂x_m    ∂mass/∂x_m = ρ Σ_k c_k ∂w_k/∂x_m
#     ∂w_m/∂x_m = q x_m^{q−1} Π_{n≠m}(1 − x_n^q),   ∂w_k/∂x_m = −w_k q x_m^{q−1} / (1 − x_m^q)  (k ≠ m)
#
# (the last written without the division, as the product over n ∉ {k, m}).  Without a
# multi-material design (no "material" field) every element is material 1.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.interpolation import Interpolation


class DMO(Interpolation):
    """Void or one of two or three materials per element, by DMO weights; stiffness and mass follow the choice."""

    name = "dmo"
    label = "Multi-material (DMO)"
    use_when = ("With the multi-material representation: each element becomes void or one of the candidate "
                "materials, trading stiffness against mass within the budget.")
    reference = ('J. Stegmann, E. Lund, "Discrete material optimization of general composite shell structures",'
                 " Int. J. Numer. Meth. Engng 62 (2005) 2009-2027 (the DMO4 weights)."
                 " Papers: https://doi.org/10.1002/nme.1259")
    order = 50
    fields = ("material",)
    nonlinear_volume = True
    params = (
        Param("penal", 3.0, "Density penalty p", "SIMP penalty of the density (topology).", min=1.0, max=6.0,
              step=0.5, decimals=2),
        Param("q", 3.0, "Mixture penalty q", "How strongly mixtures of materials are penalised.", min=1.0,
              max=6.0, step=0.5, decimals=2),
        Param("stiffness_1", 1.0, "Material 1 stiffness", "Relative to E0.", min=1e-3, max=10.0, decimals=4),
        Param("mass_1", 1.0, "Material 1 mass", "Relative mass per volume.", min=1e-3, max=10.0, decimals=4),
        Param("stiffness_2", 0.4, "Material 2 stiffness", "Relative to E0.", min=1e-3, max=10.0, decimals=4),
        Param("mass_2", 0.3, "Material 2 mass", "Relative mass per volume.", min=1e-3, max=10.0, decimals=4),
        Param("stiffness_3", 0.1, "Material 3 stiffness", "Relative to E0 (used with three materials).",
              min=1e-3, max=10.0, decimals=4),
        Param("mass_3", 0.05, "Material 3 mass", "Relative mass per volume (used with three materials).",
              min=1e-3, max=10.0, decimals=4),
    )

    def __init__(self, penal=3.0, q=3.0, stiffness_1=1.0, mass_1=1.0, stiffness_2=0.4, mass_2=0.3,
                 stiffness_3=0.1, mass_3=0.05):
        self.penal, self.q = float(penal), float(q)
        self.e = np.array([stiffness_1, stiffness_2, stiffness_3], dtype=float)
        self.c = np.array([mass_1, mass_2, mass_3], dtype=float)
        self.field_values, self.field_order = {}, "C"

    @classmethod
    def problems_with(cls, physics):
        return []

    # ── the weights ──
    def _x(self, like):
        x = self.field_values.get("material")
        if x is None:                   # no multi-material design: every element is material 1
            return None
        if x.shape[1:] != np.shape(like):           # the physics asks with a flat array
            x = np.stack([channel.reshape(-1, order=self.field_order) for channel in x])
            x = x.reshape((x.shape[0],) + np.shape(like))
        return np.clip(x, 0.0, 1.0)

    def _weights(self, x):
        """w (M, …) and dw[k, m] = ∂w_k/∂x_m (M, M, …)."""
        q, count = self.q, x.shape[0]
        power = x ** q
        dpower = q * np.where(x > 0, x ** (q - 1.0), 0.0)
        rest = 1.0 - power
        w = np.empty_like(x)
        dw = np.zeros((count,) + x.shape)
        for k in range(count):
            others = [n for n in range(count) if n != k]
            w[k] = power[k] * np.prod(rest[others], axis=0)
            for m in range(count):
                if m == k:
                    dw[k, m] = dpower[k] * np.prod(rest[others], axis=0)
                else:
                    keep = [n for n in others if n != m]
                    dw[k, m] = -power[k] * dpower[m] * (np.prod(rest[keep], axis=0) if keep else 1.0)
        return w, dw

    def _mix(self, density):
        x = self._x(density)
        if x is None:
            ones = np.ones_like(np.asarray(density, dtype=float))
            return self.e[0] * ones, self.c[0] * ones, np.zeros((1,) + ones.shape), np.zeros((1,) + ones.shape)
        w, dw = self._weights(x)
        count = x.shape[0]
        e, c = self.e[:count].reshape((count,) + (1,) * density.ndim), self.c[:count].reshape((count,) + (1,) * density.ndim)
        s, mass = np.sum(w * e, axis=0), np.sum(w * c, axis=0)
        ds = np.einsum("k...,km...->m...", w * 0 + e, dw)          # ∂s/∂x_m
        dc = np.einsum("k...,km...->m...", w * 0 + c, dw)          # ∂c/∂x_m
        return s, mass, ds, dc

    # ── the Interpolation interface ──
    def stiffness(self, density, E0, Emin):
        s, _, _, _ = self._mix(density)
        return Emin + density ** self.penal * s * (E0 - Emin)

    def slope(self, density, E0, Emin):
        s, _, _, _ = self._mix(density)
        return self.penal * np.where(density > 0, density ** (self.penal - 1.0), 0.0) * s * (E0 - Emin)

    def volume_density(self, density):
        _, mass, _, _ = self._mix(density)
        return density * mass

    def volume_slope(self, density):
        _, mass, _, _ = self._mix(density)
        return mass

    def field_slopes(self, density, E0, Emin):
        _, _, ds, _ = self._mix(density)
        return {"material": density ** self.penal * (E0 - Emin) * ds}

    def volume_field_slopes(self, density):
        _, _, _, dc = self._mix(density)
        return {"material": density * dc}
