# library/responses/volume.py — material volume.
#
# The total physical material of the design.  As an objective it gives the
# lightest design that still satisfies the scenario's constraints; on its own
# that would be an empty design, so it requires at least one constraint (for
# example stress).  The volume budget scenario.volfrac still applies as an
# upper bound and sets the starting design.
#
# Start from a full design.  Measured on the MBB beam with a stress limit:
# from volfrac 0.5 with move 0.2 the domain empties within five iterations and
# the stress constraint never recovers (peak stress 10^4 x the limit); from
# volfrac 1.0 with move 0.05 the same problem converges to 55 % material with
# the peak stress under the limit.  pyMOTO's own stress example also starts full.
#
# It needs no physics at all, so every model can offer it.

import numpy as np

from toporia.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue


class Volume(Response):
    name = "volume"
    label = "Material volume"
    order = 20
    roles = (OBJECTIVE_ROLE,)
    needs_constraint = True
    requires = ()
    advice = ("Minimising volume works best from a full design: set the volume fraction to 1.0 "
              "and use a small move limit (about 0.05). From a partly empty start, large steps "
              "can empty the domain before the constraints take hold.")

    def evaluate(self, state, gradient=True):
        density = state.density
        return ResponseValue(float(np.sum(density)), np.ones_like(density, dtype=float) if gradient else None)
