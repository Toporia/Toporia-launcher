# plugins/problems/truss_cantilever_3d.py — the 3-D cantilever as a space truss.
#
# The 3-D cantilever's scenario solved by the ground-structure truss method in 3-D:
# nodes every 5 mm, bars to every neighbour within two steps, sized for minimum
# compliance; the settled truss is drawn as cylinders on the brick mesh and its peak
# von Mises stress and compliance are checked on the H8 solver.

from toporia_core.framework import Solver

from . import cantilever_3d

NAME = "Cantilever 3D (Truss)"
ORDER = 31
ABOUT = ("The 3-D cantilever found as a space truss on a ground structure, then drawn on the brick mesh"
         " and checked for its peak stress.")
REFERENCE = ('W. S. Dorn, R. E. Gomory, H. J. Greenberg, "Automatic design of optimal structures", J. Mécanique'
             " 3 (1964) 25-52. Papers: https://doi.org/10.1007/978-3-662-05086-6")


def scenario():
    """The 3-D cantilever's physical problem, unchanged."""
    return cantilever_3d.scenario()


def solver() -> Solver:
    """The truss method in 3-D, with a stress check of the drawn design."""
    return Solver(method="truss", method_params={"spacing": 5.0, "reach": 2, "stage": "check",
                                                 "truss_iterations": 80},
                  filter_specs=[], m=0.4, max_iter=200, tol=0.01)


def _description():
    from ._truss_description import truss_description
    return truss_description(__import__(__name__, fromlist=["x"]),
                             "the truss is drawn as cylinders on the brick mesh and solved once on the H8 "
                             "solver for its compliance and peak von Mises stress.")
