# toporia_library/models/q4_mechanism.py — the compliant-mechanism Q4 engine as a model.
#
# The maths, in toporia_library/physics/q4_mechanism.py: K(ρ) u = f with fixed springs
# k_in, k_out added to the diagonal at the input and output ports (they do not depend
# on the design).  The objective is the output displacement J = −lᵀu (l picks the
# output port's DOF in the chosen direction), found with one adjoint solve K λ = l:
#     ∂J/∂ρ_e = E'(ρ_e) Σ_k w_k λ_eᵀ K_e⁰ u_ek
# Its sign changes from element to element, so pair it with MMA.

"""Q4 port-spring elasticity as a composable density model."""

from toporia_library.models.assembled import AssembledModel
from toporia_library.physics.q4_mechanism import Q4Mechanism


class Q4MechanismModel(AssembledModel):
    """Toporia's 2-D Q4 solver with input/output port springs, for compliant mechanisms such as a force inverter."""
    name = "q4_mechanism"
    label = "2-D Q4 compliant mechanism (Toporia)"
    use_when = "For compliant mechanisms (grippers, force inverters): input and output ports with springs."
    order = 13
    physics = Q4Mechanism
    reference = (
        'O. Sigmund, "On the Design of Compliant Mechanisms Using Topology Optimization", '
        'Mechanics of Structures and Machines 25 (1997) 493-524. '
        'Own linear Q4 implementation with point springs. '
        'Papers: https://doi.org/10.1080/08905459708945415'
    )
