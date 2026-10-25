# plugins/responses/thermal_compliance.py — thermal compliance of a conduction problem.
#
# C = Σ_k w_k · q_kᵀ T_k, the load-weighted heat input times the temperature it
# produces.  For uniform generation it is proportional to the average
# temperature, so minimising it keeps the part cool: it is the objective of the
# heat-sink problem, as compliance is of the structural ones.
#
# It is self-adjoint like compliance (the heat input does not depend on the
# density), so its sensitivity needs no extra solve:
#
#     dC/dρ_e = −dk/dρ_e · Σ_k w_k · T_eᵀ K_e T_e

import numpy as np

from toporia.framework.parts.physics import THERMAL_ENERGY
from toporia.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue


class ThermalCompliance(Response):
    """C = Σ w_k q_kᵀ T_k, the load-weighted thermal compliance; minimising it keeps the part cool."""
    name = "thermal_compliance"
    label = "Thermal compliance"
    reference = (
        'The objective of the heat-sink problem: M. P. Bendsoe, O. Sigmund, Topology Optimization'
        ' (Springer 2003), section 1.5; A. Gersborg-Hansen, M. P. Bendsoe, O. Sigmund, Struct.'
        ' Multidisc. Optim. 31 (2006) 251-259.'
        ' Papers: https://doi.org/10.1007/s00158-005-0584-3'
    )
    order = 12
    roles = (OBJECTIVE_ROLE,)
    requires = (THERMAL_ENERGY,)

    def evaluate(self, state, gradient=True):
        physics = self.physics
        value = 0.0
        for case, weight in enumerate(state.weights):
            value += weight * physics.thermal_compliance(state, case)
        if not gradient:
            return ResponseValue(value)

        energy = np.zeros_like(state.density, dtype=float)
        for case, weight in enumerate(state.weights):
            energy += weight * physics.thermal_energy(state, case)
        return ResponseValue(value, -physics.stiffness_slope(state) * energy)
