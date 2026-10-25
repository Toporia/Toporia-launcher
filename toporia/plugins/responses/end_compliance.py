# plugins/responses/end_compliance.py — compliance at the final load of a non-linear solve.
#
# C = Σ_k w_k · f_kᵀ u_k(ρ), where u_k solves the non-linear equilibrium
# f_int(u, ρ) = f_k.  It is the stiffness-design objective of geometrically
# non-linear topology optimisation (Buhl, Pedersen & Sigmund 2000): the work of
# the full load over the displacement it actually causes.
#
# It is not self-adjoint any more, so the engine answers with an adjoint solve,
# K_T(u) λ = f, and dC/dρ_e = −λ_eᵀ ∂R_e/∂ρ_e (framework/parts/physics.py, NONLINEAR).

import numpy as np

from toporia.framework.parts.physics import END_COMPLIANCE
from toporia.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue


class EndCompliance(Response):
    """C = Σ w_k f_kᵀ u_k at the final load of a non-linear solve; minimising it maximises stiffness there."""
    name = "end_compliance"
    label = "End compliance (non-linear)"
    reference = (
        'Stiffness design of geometrically non-linear structures: T. Buhl, C. B. W. Pedersen, O.'
        ' Sigmund, Struct. Multidisc. Optim. 19 (2000) 93-104.'
        ' Papers: https://doi.org/10.1007/s001580050089'
    )
    order = 15
    roles = (OBJECTIVE_ROLE,)
    requires = (END_COMPLIANCE,)

    def evaluate(self, state, gradient=True):
        physics = self.physics
        value = sum(weight * physics.end_compliance(state, case) for case, weight in enumerate(state.weights))
        if not gradient:
            return ResponseValue(value)
        derivative = np.zeros_like(state.density, dtype=float)
        for case, weight in enumerate(state.weights):
            derivative += weight * physics.end_compliance_sensitivity(state, case)
        return ResponseValue(value, derivative)
