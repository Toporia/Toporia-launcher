# toporia_library/models/q4_orthotropic.py — the fibre-reinforced Q4 engine as a model.
#
# Density and fibre angle per element (Wave 5): pair with the representation
# fibre_angle, which hands the engine its "angle" field, and a general-gradient updater
# (MMA).  The engine is toporia_library/physics/q4_orthotropic.py.
#
#
# The maths, in toporia_library/physics/q4_orthotropic.py: K = Σ_e E(ρ_e) K_e(θ_e) with
# K_e(θ) = K0 + cos2θ K1 + sin2θ K2 + cos4θ K3 + sin4θ K4 (Tsai–Pagano), so
# ∂C/∂ρ_e = −E'(ρ_e) Σ_k w_k u_ekᵀ K_e(θ_e) u_ek and ∂C/∂θ_e = −E(ρ_e) Σ_k w_k u_ekᵀ K_e'(θ_e) u_ek.

from toporia_library.physics.q4_orthotropic import Q4Orthotropic

from .assembled import AssembledModel


class Q4OrthotropicModel(AssembledModel):
    """Fibre-reinforced plane stress: a density and a fibre angle per element, compliance with exact gradients."""

    name = "q4_orthotropic"
    label = "2-D Q4 fibre-reinforced (angle per element)"
    use_when = ("To steer fibres along the load paths while laying out material: pair with the 'Density and fibre "
                "angle' representation and MMA.")
    reference = ('S. W. Tsai, N. J. Pagano, "Invariant properties of composite materials" (1968); continuous'
                 " fibre-angle optimisation as in T. Nomura et al., Int. J. Numer. Meth. Engng 101 (2015) 571-605."
                 " Papers: https://doi.org/10.1002/nme.4799")
    order = 18
    physics = Q4Orthotropic
