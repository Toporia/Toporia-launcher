# library/responses/stress.py — peak von Mises stress.
#
# A limit on the largest von Mises stress anywhere in the design.  The maximum
# is not differentiable, so it is approximated by the p-norm of all element
# stresses, over every load case:
#
#     g = s · ‖ ρ_e^q · σ_vm,e ‖_p / limit − 1  ≤  0
#
# The factor ρ^q (q below the SIMP penalty) relaxes the stress of low-density
# elements, so void cannot be "over-stressed" — without it the optimiser gets
# stuck on the stress singularity of vanishing material.
#
# The scale s is adaptive by default: it is reset every iteration so that the
# p-norm equals the true peak.  Without it the p-norm overestimates the peak
# (by about 38 % on the MBB beam at p = 8), so a typed limit of 4.4 behaved
# like a real limit of 3.2.  Measured on the MBB beam at a limit of 0.9 x the
# stiffest design's peak: fixed scaling ended at peak 3.42 and broke the 50 %
# volume budget (56 % material); adaptive ended at peak 4.13 against the
# limit of 4.15, within budget, and converged faster.  The drone arm and
# volume minimisation behaved the same way.
#
# The adaptive scale is treated as a constant in the gradient (as in pyMOTO
# and the literature), so the constraint shifts slightly from one iteration to
# the next and its gradient is not the exact derivative of that shifting
# function.  In practice this converged well; switch adaptive off when an
# exactly consistent gradient matters more than the limit's meaning.

from toporia.core.params import Param
from toporia.core.responses import CONSTRAINT_ROLE, Response


class VonMisesStress(Response):
    name = "stress"
    label = "Peak von Mises stress"
    order = 30
    roles = (CONSTRAINT_ROLE,)
    params = (
        Param("limit", 10.0, "Stress limit",
              "Largest allowed von Mises stress, in the scenario's units: the Young's modulus E0 "
              "and the load magnitudes set the scale.",
              min=1e-6, max=1e9, step=1.0, decimals=4),
        Param("p", 8.0, "P-norm exponent",
              "Aggregation sharpness. The p-norm of all element stresses stands in for the maximum; "
              "higher follows the peak more closely but is harder to optimise.",
              min=1.0, max=64.0, step=1.0, decimals=1),
        Param("q", 0.5, "Relaxation q",
              "Element stress is scaled by density^q, so void elements cannot be over-stressed. "
              "Keep it below the SIMP penalty.",
              min=0.0, max=3.0, step=0.1, decimals=2),
        Param("adaptive", True, "Adaptive scaling",
              "Rescale the p-norm every iteration so it matches the true peak, so the limit means "
              "what it says. Without it the p-norm overestimates the peak and the effective limit "
              "is much stricter than the number entered."),
    )
