# plugins/problems/l_bracket_stress.py — the L-bracket with a stress limit on every element.
#
# The geometry of l_bracket.py; the task is the one the benchmark exists for:
# the lightest design whose von Mises stress stays under a limit in EVERY
# element, solved by the augmented-Lagrangian method (updaters/augmented_lagrangian.py)
# with one constraint and one multiplier per element (responses/local_stress.py).
# The limit is below the stress of the compliance design (l_bracket.py) at its
# sharp re-entrant corner, so the optimiser has to round it.  Start from a full
# design with a small move limit, as for any volume-minimisation problem.
#
# What it reaches (29 October 2026, 50 x 50 cells, 800 steps): the compliance
# design's peak relaxed stress is 0.673 at 40 % material; this design needs 27 %
# and peaks at 0.5018, 0.36 % over the limit (inside the run report's 1 %).
# With a fixed move limit of 0.05 it stayed about 3 % over whatever the step
# count or penalty: the peak swung between 1.02 and 1.05 times the limit in some
# 80 elements spread over the design (not at the corner), as MMA overshot the
# moving penalty.  Shrinking the move limit (0.05 to 0.001, by 1.5 every 50
# steps) lets the multipliers settle; a penalty up to 10 000 then closes the gap.
# Like any penalty method it approaches the limit from above.

from dataclasses import replace

from toporia.framework import Solver
from toporia.plugins.problems import l_bracket

NAME = "L-bracket (local stress)"
ORDER = 71
ABOUT = ('The L-bracket again, now minimising volume under a von Mises limit in every element with the'
         ' augmented Lagrangian method: the re-entrant corner has to round off to meet the limit.'
         ' It cuts the corner peak from 0.67 to 0.50 with 27 % material, ending 0.4 % over the limit'
         " (within the run report's 1 %): a shrinking move limit lets the multipliers settle.")
REFERENCE = ('O. Giraldo-Londono and G. H. Paulino, Struct. Multidisc. Optim. 63 (2021) 2065-2097'
             ' (PolyStress). Geometry as in the L-bracket preset; the limit is chosen here.'
             ' Papers: https://doi.org/10.1007/s00158-020-02760-8')

#: The element stress limit, in the scenario's units (E0 = 1, load 1).
LIMIT = 0.5


def scenario():
    """The L-bracket, from a full design, minimising volume under the local stress limit."""
    return replace(l_bracket.scenario(), volfrac=1.0, objective={"type": "volume"},
                   constraints=[{"type": "local_stress", "limit": LIMIT, "penalty": 10.0, "penalty_max": 10000.0}])


def solver() -> Solver:
    """Augmented Lagrangian with a shrinking move limit, a density filter and a coarse mesh."""
    return Solver(method="q4+augmented_lagrangian", filter_specs=[{"type": "density"}], m=0.5,
                  max_iter=800, tol=0.0, method_params={"move": 0.05},
                  schedules=[{"path": "method.move", "type": "geometric", "start": 0.05, "end": 0.001,
                              "factor": 1.5, "every": 50}])
