# toporia_library/models/h8_heat.py — Toporia's 3-D heat-conduction solver as a model.
#
# The 3-D counterpart of q4_heat.py: element densities, the filter pipeline, a
# material law, and steady conduction on eight-node bricks
# (toporia_library/physics/h8_heat.py).  It needs a scenario with a depth (Lz > 0).
#
#
# The maths, in toporia_library/physics/h8_heat.py: K(ρ) T_k = q_k with
# K = Σ_e k(ρ_e) K_e⁰ (unit conductivity per brick), supports held at T = 0, the
# thermal compliance C_T = Σ_k w_k q_kᵀ T_k and ∂C_T/∂ρ_e = −k'(ρ_e) Σ_k w_k T_ekᵀ K_e⁰ T_ek.

from toporia_library.physics.h8_heat import H8Heat

from .assembled import AssembledModel


class H8HeatModel(AssembledModel):
    """Toporia's 3-D steady heat conduction, with the filter pipeline and thermal compliance."""

    name = "h8_heat"
    label = "3-D H8 heat conduction (Toporia)"
    use_when = "For 3-D heat-conduction design."
    reference = (
        'M. P. Bendsoe, O. Sigmund, Topology Optimization (Springer 2003), section 1.5; A.'
        ' Gersborg-Hansen, M. P. Bendsoe, O. Sigmund, "Topology optimization of heat conduction'
        ' problems using the finite volume method", Struct. Multidisc. Optim. 31 (2006) 251-259.'
        ' Papers: https://doi.org/10.1007/s00158-005-0584-3'
    )
    order = 40
    physics = H8Heat
