# plugins/responses/stress.py — peak von Mises stress.
#
# A limit on the largest von Mises stress anywhere in the design.  The maximum
# is not differentiable, so it is approximated by the p-norm of all element
# stresses, over every load case:
#
#     g = s · ‖ ρ_e^q · σ_vm,e ‖_p / limit − 1  ≤  0
#
# The factor ρ^q (q below the SIMP penalty) relaxes the stress of low-density
# elements, so void cannot be "over-stressed" — without it the optimiser gets
# stuck on the stress singularity of vanishing material.
#
# The scale s is adaptive by default: it is reset every iteration so that the
# p-norm equals the true peak.  Without it the p-norm overestimates the peak
# (by about 38 % on the MBB beam at p = 8), so a typed limit of 4.4 behaved
# like a real limit of 3.2.  Measured on the MBB beam at a limit of 0.9 x the
# stiffest design's peak: fixed scaling ended at peak 3.42 and broke the 50 %
# volume budget (56 % material); adaptive ended at peak 4.13 against the
# limit of 4.15, within budget, and converged faster.  The drone arm and
# volume minimisation behaved the same way.
#
# The adaptive scale is treated as a constant in the gradient (as in pyMOTO
# and the literature), so the constraint shifts slightly from one iteration to
# the next and its gradient is not the exact derivative of that shifting
# function.  In practice this converged well; switch adaptive off when an
# exactly consistent gradient matters more than the limit's meaning.
#
# The sensitivity needs one adjoint solve per load case.  With r_e = ρ_e^q σvm_e
# and P = ‖r‖_p:
#
#     ∂P/∂r_e = (r_e / P)^(p−1)
#     explicit    ∂P/∂ρ_e  via  q ρ_e^(q−1) σvm_e
#     adjoint     K λ = Σ_e ∂P/∂r_e · ρ_e^q · ∂σvm_e/∂u          (physics.stress_load)
#                 dP/dρ_e −= dE/dρ_e · λ_eᵀ K_e u_e              (physics.mutual_energy)
#
# Everything engine-specific — element stresses, the adjoint solve — comes from
# the physics engine (framework/parts/physics.py), so this one file serves every engine
# that provides the STRESS feature.
#
# Stresses are measured with the true element size, so a limit means the same
# at every mesh resolution.  The pyMOTO model's stresses differ from these in
# two ways, both pinned by tests/plugins/test_physics.py:
#   * pyMOTO measures on unit elements, so its strains are m times smaller
#     than the true ones at a mesh of m el/mm (equal at m = 1);
#   * pyMOTO 2.0.1 doubles the shear stress: its strain-displacement matrix
#     already gives the engineering shear γ = ∂u/∂y + ∂v/∂x, and Strain(voigt=True)
#     doubles that row again.  Its von Mises stress is therefore too high
#     wherever there is shear (by 22 % on a random MBB design).

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.physics import STRESS
from toporia.framework.parts.response import CONSTRAINT_ROLE, Response, ResponseValue

# 2-D plane-stress von Mises from Voigt stress s = [sxx, syy, txy]:  vm² = sᵀ V s
VON_MISES_2D = np.array([[1.0, -0.5, 0.0], [-0.5, 1.0, 0.0], [0.0, 0.0, 3.0]])
# Keeps the square root differentiable where an element carries no stress.
_EPSILON = 1e-12


class VonMisesStress(Response):
    """A limit on the peak von Mises stress, through a p-norm of the relaxed element stresses."""
    name = "stress"
    label = "Peak von Mises stress"
    order = 30
    roles = (CONSTRAINT_ROLE,)
    params = (
        Param("limit", 10.0, "Stress limit",
              "Largest allowed von Mises stress, in the scenario's units: the Young's modulus E0 "
              "and the load magnitudes set the scale.",
              min=1e-6, max=1e9, step=1.0, decimals=4),
        Param("p", 8.0, "P-norm exponent",
              "Aggregation sharpness. The p-norm of all element stresses stands in for the maximum; "
              "higher follows the peak more closely but is harder to optimise.",
              min=1.0, max=64.0, step=1.0, decimals=1),
        Param("q", 0.5, "Relaxation q",
              "Element stress is scaled by density^q, so void elements cannot be over-stressed. "
              "Keep it below the SIMP penalty.",
              min=0.0, max=3.0, step=0.1, decimals=2),
        Param("adaptive", True, "Adaptive scaling",
              "Rescale the p-norm every iteration so it matches the true peak, so the limit means "
              "what it says. Without it the p-norm overestimates the peak and the effective limit "
              "is much stricter than the number entered."),
    )

    requires = (STRESS,)
    # A larger p-norm exponent once the design has settled approximates the peak better.
    schedulable = ("p",)
    #: The adaptive scale is held constant in the gradient on purpose (see above),
    #: so the gradient is checked against finite differences with it switched off.
    gradient_check_settings = {"adaptive": False}

    def evaluate(self, state, gradient=True):
        physics, settings = self.physics, self.settings
        # The squared von Mises stress is σᵀVσ; a 3-D engine brings its own 6 × 6 V.
        vm = getattr(physics, "von_mises_matrix", VON_MISES_2D)
        p, q, limit = settings["p"], settings["q"], settings["limit"]
        density = state.density
        relaxation = density ** q

        cases = []   # (stress, von Mises, relaxed von Mises) per load case
        for case in range(len(state.weights)):
            stress = physics.element_stress(state, case)
            von_mises = np.sqrt(np.einsum("...i,ij,...j->...", stress, vm, stress) + _EPSILON)
            cases.append((stress, von_mises, relaxation * von_mises))

        peak = float(max(np.max(relaxed) for *_, relaxed in cases))
        # The p-norm, computed relative to the peak so that r^p cannot overflow.
        norm = peak * float(sum(np.sum((relaxed / peak) ** p) for *_, relaxed in cases)) ** (1.0 / p)
        scale = peak / norm if settings["adaptive"] else 1.0
        value = scale * norm / limit - 1.0
        exact = peak / limit - 1.0
        reported = {"max_stress": peak}
        if not gradient:
            return ResponseValue(value, None, exact, reported)

        # d(ρ^q)/dρ, taken as 0 where the density is exactly 0 (its limit is
        # infinite for q < 1, and such an element carries no stress anyway).
        d_relaxation = np.zeros_like(density, dtype=float)
        solid = density > 0
        d_relaxation[solid] = q * density[solid] ** (q - 1.0)
        slope = physics.stiffness_slope(state)

        sensitivity = np.zeros_like(density, dtype=float)
        for case, (stress, von_mises, relaxed) in enumerate(cases):
            d_norm = (relaxed / norm) ** (p - 1.0)
            sensitivity += d_norm * d_relaxation * von_mises
            d_stress = (d_norm * relaxation / von_mises)[..., None] * (stress @ vm)
            adjoint = physics.adjoint(state, physics.stress_load(state, case, d_stress))
            sensitivity -= slope * physics.mutual_energy(state, case, adjoint)
        return ResponseValue(value, scale / limit * sensitivity, exact, reported)
