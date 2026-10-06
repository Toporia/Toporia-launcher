# plugins/models/q4.py — Toporia's own 2-D Q4 solver as a model.
#
# Design variable: x[i, j] ∈ [0, 1], the density of element (i, j) before
# filtering.  The filter pipeline turns it into the physical density, SIMP
# turns that into stiffness, and the Q4 solver gives the state every response
# is computed from:
#
#     x ──filters──> ρ ──SIMP: E = Emin + ρ^p (E0 − Emin)──> K ──solve──> u ──> compliance, stress, ...
#
# All of that is assembled from parts (plugins/models/assembled.py); this
# file only says which physics engine to use.  It is the physics half of the
# top88 code by Andreassen et al. (2011); the update half (OC, MMA, ...)
# lives in plugins/updaters.

from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress

from .assembled import AssembledModel


class Q4Model(AssembledModel):
    """Toporia's 2-D Q4 plane-stress solver, with the filter pipeline and every response it supports."""

    name = "q4"
    label = "2-D Q4 plane stress (Toporia)"
    aliases = ("q4_compliance",)   # its name while it could only minimise compliance
    order = 10
    physics = Q4PlaneStress
