# library/responses/compliance.py — structural compliance.
#
# C = Σ_k w_k · f_kᵀ u_k, the load-weighted work of the external forces over
# the load cases.  Minimising it maximises stiffness; it is the objective of
# every classic benchmark (MBB, cantilever) and the default.
#
# Compliance is self-adjoint, so its sensitivity needs no extra solve:
#
#     dC/dρ_e = −dE/dρ_e · Σ_k w_k · u_eᵀ K_e u_e

import numpy as np

from toporia.framework.parts.physics import ELASTIC_ENERGY
from toporia.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue


class Compliance(Response):
    name = "compliance"
    label = "Compliance"
    order = 10
    roles = (OBJECTIVE_ROLE,)
    requires = (ELASTIC_ENERGY,)

    def evaluate(self, state, gradient=True):
        physics = self.physics
        value = 0.0
        for case, weight in enumerate(state.weights):
            value += weight * physics.compliance(state, case)
        if not gradient:
            return ResponseValue(value)

        energy = np.zeros_like(state.density, dtype=float)
        for case, weight in enumerate(state.weights):
            energy += weight * physics.strain_energy(state, case)
        return ResponseValue(value, -physics.stiffness_slope(state) * energy)
