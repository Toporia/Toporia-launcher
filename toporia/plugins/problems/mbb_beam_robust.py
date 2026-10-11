# plugins/problems/mbb_beam_robust.py — the MBB beam, designed robustly (three-field projection).
#
# The same scenario as mbb_beam.py, but every design is projected three times
# (eroded eta = 0.75, intermediate 0.5, dilated 0.25) and the worst of the three
# compliances is minimised, so the result keeps its minimum length scale when
# the part is made slightly too thin or too thick.  The projection sharpness
# beta follows the `geometric` schedule 1 -> 64 (doubled every 25 iterations).
#
# This is a ready-made recipe, not new mathematics: solver.variants
# (framework/parts/variants.py) and a schedule (plugins/schedules/geometric.py).
# Differences from the paper (volume held on the intermediate design, a smooth
# maximum instead of one constraint per variant) are listed in variants.py.
#
# Reference: F. Wang, B. S. Lazarov, O. Sigmund, "On projection methods,
# convergence and robust formulations in topology optimization",
# SMO 43 (2011) 767–784.

from toporia.framework import Solver

from . import mbb_beam

NAME = "MBB Beam (Robust)"
ORDER = 15


def scenario():
    """The MBB beam's physical problem, unchanged."""
    return mbb_beam.scenario()


def solver() -> Solver:
    """Density filter, then Heaviside projection (filters[1]), evaluated eroded / intermediate / dilated."""
    return Solver(
        method="q4+oc",
        filter_specs=[{"type": "density"}, {"type": "heaviside", "beta": 1.0, "eta": 0.5}],
        schedules=[{"path": "filters[1].beta", "type": "geometric", "start": 1.0, "end": 64.0,
                    "factor": 2.0, "every": 25}],
        variants={"path": "filters[1].eta", "values": [0.75, 0.5, 0.25], "combine": "worst", "nominal": 1},
        m=1.0, max_iter=200, tol=0.01,
    )
