# plugins/models/h8_heat.py — Toporia's 3-D heat-conduction solver as a model.
#
# The 3-D counterpart of q4_heat.py: element densities, the filter pipeline, a
# material law, and steady conduction on eight-node bricks
# (plugins/physics/h8_heat.py).  It needs a scenario with a depth (Lz > 0).

from toporia.plugins.physics.h8_heat import H8Heat

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
