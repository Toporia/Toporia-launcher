# toporia_library/responses/compliance.py — structural compliance.
#
# C = Σ_k w_k · f_kᵀ u_k, the load-weighted work of the external forces over
# the load cases.  Minimising it maximises stiffness; it is the objective of
# every classic benchmark (MBB, cantilever) and the default.
#
# Compliance is self-adjoint, so its sensitivity needs no extra solve:
#
#     dC/dρ_e = −dE/dρ_e · Σ_k w_k · u_eᵀ K_e u_e

import numpy as np

from toporia_core.framework.parts.physics import ELASTIC_ENERGY
from toporia_core.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue


class Compliance(Response):
    """C = Σ w_k f_kᵀ u_k, the load-weighted compliance; minimising it maximises stiffness."""
    name = "compliance"
    label = "Compliance"
    use_when = "The standard objective: the stiffest structure for the given loads and material budget."
    reference = (
        'The classic objective of topology optimisation: M. P. Bendsoe, O. Sigmund, Topology'
        ' Optimization: Theory, Methods and Applications, Springer 2003.'
        ' Papers: https://doi.org/10.1007/978-3-662-05086-6'
    )
    order = 10
    roles = (OBJECTIVE_ROLE,)
    requires = (ELASTIC_ENERGY,)

    handles_fields = True

    def field_gradient(self, state, name):
        """dC/d(field) for a design of several fields per element (Wave 5).

        Self-adjoint, so no extra solve.  A field of the material law (candidate-material
        weights) changes only E_e:  dC/df = −(∂E/∂f) · Σ_k w_k e_k  with e_k the unit-E
        element energy.  A field of the physics (a fibre angle) changes the element matrix:
        dC/df = −Σ_k w_k E_e u_eᵀ (∂K_e/∂f) u_e, which the physics gives (field_energy).
        """
        physics = self.physics
        material = getattr(physics, "material", None)
        if material is not None and name in getattr(material, "fields", ()):
            scenario = physics.problem.scenario
            slope = material.field_slopes(state.density, scenario.E0, scenario.Emin)[name]
            energy = np.zeros_like(state.density, dtype=float)
            for case, weight in enumerate(state.weights):
                energy += weight * physics.strain_energy(state, case)
            return -slope * energy
        return -sum(weight * physics.field_energy(state, case, name) for case, weight in enumerate(state.weights))

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
