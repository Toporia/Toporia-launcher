# library/responses/compliance.py — structural compliance.
#
# C = Σ_k w_k · f_kᵀ u_k, the load-weighted work of the external forces over
# the load cases.  Minimising it maximises stiffness; it is the objective of
# every classic benchmark (MBB, cantilever) and the default.

from toporia.core.responses import OBJECTIVE_ROLE, Response


class Compliance(Response):
    name = "compliance"
    label = "Compliance"
    order = 10
    roles = (OBJECTIVE_ROLE,)
