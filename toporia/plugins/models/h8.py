# plugins/models/h8.py — Toporia's own 3-D solver as a model.
#
# The 3-D counterpart of q4.py: element densities, the filter pipeline, a
# material law, and linear elasticity on eight-node bricks
# (plugins/physics/h8_solid.py).  It needs a scenario with a depth (Lz > 0);
# every updater, filter, schedule, variant and post-processor that works in
# 3-D works with it.

from toporia.plugins.physics.h8_solid import H8Solid

from .assembled import AssembledModel


class H8Model(AssembledModel):
    """Toporia's 3-D H8 solver, with the filter pipeline and every response it supports."""

    name = "h8"
    label = "3-D H8 bricks (Toporia)"
    use_when = "For 3-D parts. Much slower than 2-D; start with a coarse mesh."
    reference = (
        'K. Liu, A. Tovar, "An efficient 3D topology optimization code written in Matlab", Struct.'
        ' Multidisc. Optim. 50 (2014) 1175-1196 (top3d).'
        ' Papers: https://doi.org/10.1007/s00158-014-1107-x'
    )
    order = 15
    physics = H8Solid
