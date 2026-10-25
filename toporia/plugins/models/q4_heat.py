# plugins/models/q4_heat.py — Toporia's 2-D heat-conduction solver as a model.
#
# Design variable: x[i, j] ∈ [0, 1], the density of element (i, j) before
# filtering.  The filter pipeline turns it into the physical density, the
# material law turns that into conductivity, and the Q4 conduction solver gives
# the temperature field the thermal compliance is computed from:
#
#     x ──filters──> ρ ──SIMP: k = kmin + ρ^p (k0 − kmin)──> K ──solve──> T ──> thermal compliance qᵀT
#
# All of that is assembled from parts (plugins/models/assembled.py); this file
# only says which physics engine to use.  Supports are heat sinks (T = 0).

from toporia.plugins.physics.q4_heat import Q4Heat

from .assembled import AssembledModel


class Q4HeatModel(AssembledModel):
    """Toporia's 2-D steady heat conduction, with the filter pipeline and thermal compliance."""

    name = "q4_heat"
    label = "2-D Q4 heat conduction (Toporia)"
    reference = (
        'M. P. Bendsoe, O. Sigmund, Topology Optimization (Springer 2003), section 1.5; A.'
        ' Gersborg-Hansen, M. P. Bendsoe, O. Sigmund, "Topology optimization of heat conduction'
        ' problems using the finite volume method", Struct. Multidisc. Optim. 31 (2006) 251-259.'
        ' Papers: https://doi.org/10.1007/s00158-005-0584-3'
    )
    order = 30
    physics = Q4Heat
