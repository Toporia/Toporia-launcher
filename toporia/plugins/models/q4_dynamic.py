# plugins/models/q4_dynamic.py — Toporia's 2-D Q4 solver with vibration, as a model.
#
# The same assembly as q4.py (filters, material law, every static response), on an
# engine that also has a mass matrix (plugins/physics/q4_dynamic.py), so it offers
# two more things to optimise:
#
#     x ──filters──> ρ ──> K(ρ), M(ρ) ──> eigenfrequencies  K φ = λ M φ   (response: eigenfrequency)
#                                     └──> harmonic response (K − ω² M) u = f  (response: dynamic_compliance)
#
# Sensitivities of eigenvalues change sign, so pair it with MMA: "q4_dynamic+mma".

from toporia.plugins.physics.q4_dynamic import Q4Dynamic

from .assembled import AssembledModel


class Q4DynamicModel(AssembledModel):
    """Toporia's 2-D Q4 solver with a mass matrix: maximise a natural frequency, or minimise a harmonic response."""

    name = "q4_dynamic"
    label = "2-D Q4 with vibration (Toporia)"
    reference = (
        'Mass interpolation that avoids spurious low-density modes: N. L. Pedersen, "Maximization of'
        ' eigenvalues using topology optimization", Struct. Multidisc. Optim. 20 (2000) 2-11; its use for the'
        ' fundamental frequency: J. Du, N. Olhoff, Struct. Multidisc. Optim. 34 (2007) 91-110.'
        ' Papers: https://doi.org/10.1007/s001580050130 https://doi.org/10.1007/s00158-007-0101-y'
    )
    order = 11
    physics = Q4Dynamic
