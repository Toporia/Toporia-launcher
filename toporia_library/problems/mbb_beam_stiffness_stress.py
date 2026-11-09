# toporia_library/problems/mbb_beam_stiffness_stress.py — the MBB beam, stiff and with a low peak stress.
#
# The MBB beam's scenario with a combined objective (toporia_library/responses/combined.py):
# the weighted sum of compliance and the peak von Mises stress (its p-norm, p = 8), each
# divided by its value at the start design.  Compliance alone puts sharp re-entrant
# corners where the load meets the members; the stress term rounds them off at a small
# cost in stiffness.  The weight 0.5 on stress is a demonstration, not a tuned value.
#
# MMA, because the combined sensitivities are not all of one sign (OC assumes they are).

from toporia_core.framework import Solver

from . import mbb_beam

NAME = "MBB Beam (Stiffness and Stress)"
ORDER = 16
ABOUT = ("The MBB beam with two goals at once: stiff, and a low peak stress. A combined objective weighs"
         " compliance against the peak von Mises stress, each relative to its value at the start.")
REFERENCE = ("Weighted-sum multi-objective formulation: R. T. Marler, J. S. Arora, Struct. Multidisc. Optim."
             " 26 (2004) 369-395; p-norm stress: C. Le et al., Struct. Multidisc. Optim. 41 (2010) 605-620."
             " Demonstration preset; weights chosen here."
             " Papers: https://doi.org/10.1007/s00158-003-0368-6 https://doi.org/10.1007/s00158-009-0440-y")


def scenario():
    """The MBB beam, minimising compliance and peak stress together."""
    from dataclasses import replace
    return replace(mbb_beam.scenario(), objective={
        "type": "combined", "combine": "sum",
        "terms": [{"type": "compliance", "weight": 1.0}, {"type": "peak_stress", "weight": 0.5, "p": 8.0}]})


def solver() -> Solver:
    """MMA with a density filter on the classic 60 x 20 mesh."""
    return Solver(method="q4+mma", filter_specs=[{"type": "density"}], m=1.0, max_iter=200, tol=0.01)
