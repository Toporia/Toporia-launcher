# plugins/responses/dynamic_compliance.py — compliance under a harmonic load.
#
# A load f cos(ωt) of driving frequency ω makes the structure vibrate with the
# amplitude u of  (K − ω² M) u = f.  The dynamic compliance
#
#     C(ω) = Σ_k w_k | f_kᵀ u_k |
#
# is the work of the load over one cycle: small where the structure is stiff
# and not near a resonance.  At ω = 0 it is the static compliance.  Minimising
# it at a given ω stiffens the structure against that excitation.
#
# The matrix A = K − ω² M is symmetric, so the problem is self-adjoint and the
# sensitivity needs no extra solve:
#
#     d(fᵀu)/dρ_e = −u_eᵀ (dE/dρ_e K_e − ω² dm/dρ_e M_e) u_e
#
# (physics.dynamic_compliance_sensitivity), times the sign of fᵀu for |·|.
#
# The driving frequency should lie below the first eigenfrequency of the
# structure: at a resonance A is singular and C blows up; past it the sign of
# fᵀu flips and the optimiser can try to pass a resonance instead of stiffening.
# There is no damping, so the response is exact only away from resonances.
#
# References: the frequency-response objective of Z.-D. Ma, N. Kikuchi, I. Hagiwara,
# "Structural topology and shape optimization for a frequency response problem",
# Comput. Mech. 13 (1993) 157-174 (cited from memory, no link checked); the
# adjoint as in PolyDyna, R. Giraldo-Londoño, G. H. Paulino, SMO 64 (2021) 957-990.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.physics import HARMONIC
from toporia.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue


class DynamicCompliance(Response):
    """C(ω) = Σ w |fᵀu| with (K − ω² M) u = f: the compliance of a harmonic load of angular frequency ω."""

    name = "dynamic_compliance"
    label = "Dynamic compliance (harmonic load)"
    reference = (
        'Frequency-domain adjoint and implementation: R. Giraldo-Londono, G. H. Paulino, "PolyDyna: a'
        ' Matlab implementation for topology optimization of structures subjected to dynamic loads",'
        ' Struct. Multidisc. Optim. 64 (2021) 957-990; the objective goes back to Ma, Kikuchi and Hagiwara'
        ' (Comput. Mech. 13 (1993) 157-174).'
        ' Papers: https://doi.org/10.1007/s00158-021-02859-6'
    )
    order = 15
    roles = (OBJECTIVE_ROLE,)
    requires = (HARMONIC,)
    params = (
        Param("omega", 0.01, "Driving frequency ω",
              "Angular frequency of the harmonic load, in the units of the model (the square root of an "
              "eigenvalue λ). Keep it below the first eigenfrequency; 0 is the static compliance.",
              min=0.0, max=1e6, step=0.005, decimals=5, units="rad/s"),
    )
    advice = ("Choose the driving frequency below the first eigenfrequency of the design (compare with the "
              "eigenfrequency response): at a resonance the dynamic compliance is unbounded.")

    def evaluate(self, state, gradient=True):
        omega = self.settings["omega"]
        value = 0.0
        total = np.zeros_like(state.density, dtype=float) if gradient else None
        for case, weight in enumerate(state.weights):
            raw = self.physics.dynamic_compliance(state, case, omega)
            value += weight * abs(raw)
            if gradient:
                total += weight * np.sign(raw) * self.physics.dynamic_compliance_sensitivity(state, case, omega)
        return ResponseValue(value, total)
