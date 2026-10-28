"""HS bulk/shear upper envelope along the solver's fixed-Poisson-ratio ray.

Two well-ordered isotropic phases share scenario nu; moduli are E0 and Emin.
For each channel M (bulk or shear), the HS upper bound can be written as
Mmin + (M0-Mmin)*rho/[1+q_M*(1-rho)], q_M=(M0-Mmin)/(Mmin+a_M).
Scaling E at fixed nu scales both channels, so max(q_bulk,q_shear) enforces
both upper bounds. This is not the variable-nu interpolation of Bendsoe &
Sigmund (1999), eq.17, nor a guarantee of microstructure realisability.

2-D uses plane-stress bulk k=E/[2(1-nu)], g=E/[2(1+nu)], a_k=g,
a_g=k*g/(k+2*g). 3-D uses k=E/[3(1-2nu)], a_k=4g/3,
a_g=g*(9k+8g)/[6(k+2g)]. The finite soft phase is included in q: Emin
is not added on top of a void-limit bound. setup(problem) is mandatory.
"""

import numpy as np

from toporia.framework.parts.interpolation import Interpolation
from toporia.framework.parts.physics import ELASTIC_ENERGY, END_COMPLIANCE


class HashinShtrikman(Interpolation):
    """Fixed-nu isotropic upper envelope constrained by both HS channels."""

    name = "hashin_shtrikman"
    label = "Hashin-Shtrikman upper envelope (fixed nu)"
    use_when = (
        "When intermediate densities should be physically realisable composites: it bounds stiffness by "
        "the Hashin-Shtrikman limit instead of an arbitrary power law."
    )
    order = 50
    dims = (2, 3)
    reference = (
        'M. P. Bendsoe and O. Sigmund, "Material interpolation schemes in topology '
        'optimization", Arch. Appl. Mech. 69 (1999) 635-654, sections 3.2/3.4. '
        'Independent fixed-nu envelope of HS bulk/shear upper bounds, including '
        'a finite soft phase. Not eq.17 variable nu or certified realisability. '
        'Papers: https://doi.org/10.1007/s004190050248 '
        'https://sepwww.stanford.edu/sep/berryman/PS/PHYS.pdf'
    )

    def __init__(self):
        self.nu = self.dimension = None

    def setup(self, problem):
        nu = problem.scenario.nu
        if not np.isfinite(nu) or not -1 < nu < .5:
            raise ValueError("Hashin-Shtrikman requires a finite solid Poisson ratio -1 < nu < 0.5")
        self.nu = float(nu)
        self.dimension = len(problem.shape)
        if self.dimension not in self.dims:
            raise ValueError("Hashin-Shtrikman supports plane stress (2-D) and solid elasticity (3-D)")

    @classmethod
    def problems_with(cls, physics):
        if not {ELASTIC_ENERGY, END_COMPLIANCE}.intersection(physics.provides):
            return ["Hashin-Shtrikman is an elastic bulk/shear law; choose a mechanical model or another material law"]
        return []

    def _q(self, E0, Emin):
        if self.nu is None:
            raise ValueError("Call HashinShtrikman.setup(problem) to bind scenario nu and dimension")
        if not np.isfinite(E0) or not np.isfinite(Emin) or not 0 <= Emin <= E0 or E0 <= 0:
            raise ValueError("Hashin-Shtrikman requires finite 0 <= Emin <= E0 and E0 > 0")
        nu = self.nu
        shear = 1 / (2 * (1 + nu))
        if self.dimension == 2:
            bulk = 1 / (2 * (1 - nu))
            a_bulk, a_shear = shear, bulk * shear / (bulk + 2 * shear)
        else:
            bulk = 1 / (3 * (1 - 2 * nu))
            a_bulk, a_shear = 4 * shear / 3, shear * (9 * bulk + 8 * shear) / (6 * (bulk + 2 * shear))
        ratio = Emin / E0
        return max((1 - ratio) / (ratio + a_bulk / bulk),
                   (1 - ratio) / (ratio + a_shear / shear))

    def stiffness(self, density, E0, Emin):
        rho = np.asarray(density)
        return Emin + (E0 - Emin) * rho / (1 + self._q(E0, Emin) * (1 - rho))

    def slope(self, density, E0, Emin):
        q = self._q(E0, Emin)
        return (E0 - Emin) * (1 + q) / (1 + q * (1 - np.asarray(density))) ** 2
