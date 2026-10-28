# plugins/models/q4_nonlinear.py — Toporia's 2-D Q4 large-deformation solver as a model.
#
# Same design chain as the linear q4 model, with the geometrically non-linear engine
# (physics/q4_nonlinear.py) in place of the linear one:
#
#     x ──filters──> ρ ──SIMP──> E(ρ), blended with the linear law at low ρ ──Newton, load steps──> u
#       ──> end compliance fᵀu at the final load (responses/end_compliance.py)
#
# Large displacements, small strains: total Lagrangian, Green–Lagrange strain, St Venant–Kirchhoff
# material.  pyMOTO has no geometrically non-linear module, so there is no pyMOTO counterpart.

from toporia.plugins.physics.q4_nonlinear import Q4Nonlinear

from .assembled import AssembledModel


class Q4NonlinearModel(AssembledModel):
    """Toporia's 2-D Q4 solver with large displacements: end compliance and volume, any filter."""

    name = "q4_nonlinear"
    label = "2-D Q4, large deformation (Toporia)"
    use_when = (
        "When loads cause large displacements, so the linear model mispredicts the stiffness. Slower "
        "(Newton solves per iteration)."
    )
    reference = (
        'Stiffness design with large displacements: T. Buhl, C. B. W. Pedersen, O. Sigmund,'
        ' "Stiffness design of geometrically nonlinear structures using topology optimization",'
        ' Struct. Multidisc. Optim. 19 (2000) 93-104; void treated by an energy interpolation after'
        ' Q. Wang, B. S. Lazarov, O. Sigmund, J. S. Jensen, "Interpolation scheme for fictitious domain'
        ' techniques and topology optimization of finite strain elastic problems", CMAME 276 (2014)'
        ' 453-472. Open reference code: the 137-line BESO code of Han et al. (2021).'
        ' Papers: https://doi.org/10.1007/s001580050089 https://doi.org/10.1016/j.cma.2014.03.021'
        ' https://doi.org/10.1007/s00158-020-02816-9'
    )
    order = 11
    physics = Q4Nonlinear
