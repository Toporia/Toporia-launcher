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
    order = 15
    physics = H8Solid
