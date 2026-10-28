# plugins/problems/mbb_beam_robust.py — the MBB beam, designed robustly (three-field projection).
#
# The same scenario as mbb_beam.py, but every design is projected three times
# (eroded eta = 0.75, intermediate 0.5, dilated 0.25) and the worst of the three
# compliances is minimised through a smooth maximum. This independent recipe
# does not certify a minimum feature size or manufacturing tolerance. The projection sharpness
# beta follows the `geometric` schedule 1 -> 64 (doubled every 25 iterations).
#
# The updater is MMA with move 0.1, as in the paper. With OC at its default move 0.2,
# design variables where the projection is flat bounce by the full move every
# iteration; at high beta they cross the threshold and members of the eroded
# design flip (worst case 214 -> 1.2e8 at the 200-iteration cap). With MMA the run
# converges in about 184 iterations to a worst case near 198, black and white.
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
ABOUT = ('The MBB beam solved robustly: the worst of the eroded, intermediate and dilated designs'
         ' (Heaviside thresholds 0.75 / 0.5 / 0.25), with a doubling continuation of the sharpness.')
REFERENCE = ('F. Wang, B. S. Lazarov and O. Sigmund, "On projection methods, convergence and robust'
             ' formulations in topology optimization", Struct. Multidisc. Optim. 43 (2011) 767-784.'
             ' Independent recipe; thresholds match Fig. 6, but volume, aggregation and continuation differ.'
             ' Papers: https://doi.org/10.1007/s00158-010-0602-y'
             ' Correction: https://doi.org/10.1007/s00158-022-03326-6')


def scenario():
    """The MBB beam's physical problem, unchanged."""
    return mbb_beam.scenario()


def solver() -> Solver:
    """Density filter, then Heaviside projection (filters[1]), evaluated eroded / intermediate / dilated."""
    return Solver(
        method="q4+mma", method_params={"move": 0.1},
        filter_specs=[{"type": "density"}, {"type": "heaviside", "beta": 1.0, "eta": 0.5}],
        schedules=[{"path": "filters[1].beta", "type": "geometric", "start": 1.0, "end": 64.0,
                    "factor": 2.0, "every": 25}],
        variants={"path": "filters[1].eta", "values": [0.75, 0.5, 0.25], "combine": "worst", "nominal": 1},
        m=1.0, max_iter=300, tol=0.01,
    )
