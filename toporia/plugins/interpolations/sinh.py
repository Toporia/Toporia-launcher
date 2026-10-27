"""Bruns (2005), basic SINH equations 22-23: linear stiffness, taxed volume.

eta1=rho; eta2=1-sinh(p*(1-rho))/sinh(p). The shared filtered density feeds
both measures (Table 2 case 5 when a density filter is selected). This is
not case 6's separate resource-only filter or the hybrid stiffness penalty.
The p=0 limit is linear in both measures. Effective cost is not geometric
volume at intermediate density; both are reported separately by the model.
"""

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.interpolation import Interpolation


class SINH(Interpolation):
    """Basic SINH: intermediate material costs more than its stiffness fraction."""

    name = "sinh"
    label = "SINH (linear stiffness, penalised volume)"
    order = 40
    nonlinear_volume = True
    params = (Param("penal", 3., "Volume penalty p", "Zero gives linear volume. Larger values tax gray material.",
                    min=0., max=20., step=.1, decimals=2),)
    schedulable = ("penal",)
    reference = (
        'T. E. Bruns, "A reevaluation of the SIMP method with filtering and an alternative '
        'formulation for solid-void topology optimization", SMO 30 (2005) 428-436, equations '
        '22-23. Shared filtered-density variant (Table 2 case 5), not resource-only filtering '
        'or hybrid SINH. Effective volume differs from geometric density. '
        'Papers: https://doi.org/10.1007/s00158-005-0537-x'
    )

    def __init__(self, penal=3.):
        if not np.isfinite(penal) or not 0 <= penal <= 20:
            raise ValueError("SINH penal must be finite and in [0,20]")
        self.penal = float(penal)

    def stiffness(self, density, E0, Emin):
        return Emin + np.asarray(density) * (E0 - Emin)

    def slope(self, density, E0, Emin):
        return np.full_like(density, E0 - Emin, dtype=float)

    def volume_density(self, density):
        rho = np.asarray(density)
        p = self.penal
        if p == 0:
            return rho
        # Equivalent formulas avoid cancellation near void in the value and
        # near solid in directional derivatives at large p.
        near_void = 2 * np.cosh(p * (1 - rho / 2)) * np.sinh(p * rho / 2) / np.sinh(p)
        near_solid = 1 - np.sinh(p * (1 - rho)) / np.sinh(p)
        return np.where(rho.real <= .5, near_void, near_solid)

    def volume_slope(self, density):
        p = self.penal
        if p == 0:
            return np.ones_like(density, dtype=float)
        return p * np.cosh(p * (1 - np.asarray(density))) / np.sinh(p)
