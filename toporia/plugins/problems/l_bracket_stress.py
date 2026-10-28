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
# What it reaches (28 October 2026, 50 x 50 cells, 300 steps): the compliance
# design's peak relaxed stress is 0.673 at 40 % material; this design needs 26 %
# and peaks at 0.514, about 3 % over the limit.  The excess sits at the corner
# and stays near 3 % with 600 steps, a penalty up to 10 000, longer inner loops
# or a limit of 0.55: the sum-of-squares penalty tolerates a few elements just
# over, and the corner's stress is singular (14 % over on a 100 x 100 mesh).
# Read the peak from the report; the limit is approached, not certified.

from dataclasses import replace

from toporia.framework import Solver
from toporia.plugins.problems import l_bracket

NAME = "L-bracket (local stress)"
ORDER = 71
ABOUT = ('The L-bracket again, now minimising volume under a von Mises limit in every element with the'
         ' augmented Lagrangian method: the re-entrant corner has to round off to meet the limit.'
         ' It cuts the corner peak from 0.67 to 0.51 with 26 % material, ending about 3 % over the limit:'
         ' the corner stress is singular, so the limit is approached rather than met.')
REFERENCE = ('O. Giraldo-Londono and G. H. Paulino, Struct. Multidisc. Optim. 63 (2021) 2065-2097'
             ' (PolyStress). Geometry as in the L-bracket preset; the limit is chosen here.'
             ' Papers: https://doi.org/10.1007/s00158-020-02760-8')

#: The element stress limit, in the scenario's units (E0 = 1, load 1).
LIMIT = 0.5


def scenario():
    """The L-bracket, from a full design, minimising volume under the local stress limit."""
    return replace(l_bracket.scenario(), volfrac=1.0, objective={"type": "volume"},
                   constraints=[{"type": "local_stress", "limit": LIMIT, "penalty": 10.0, "penalty_max": 1000.0}])


def solver() -> Solver:
    """Augmented Lagrangian with small move limits, a density filter and a coarse mesh."""
    return Solver(method="q4+augmented_lagrangian", filter_specs=[{"type": "density"}], m=0.5,
                  max_iter=300, tol=0.0, method_params={"move": 0.05})
