# plugins/problems/truss_cantilever_3d.py — the 3-D cantilever as a space truss, made into a solid.
#
# The 3-D cantilever's scenario solved by the ground-structure truss method in 3-D: nodes
# every 5 mm, bars to every neighbour within two steps, sized for minimum compliance.  At
# the end the post-processor truss_solid makes the bars into one STL surface: rods of their
# cross-section joined by balls.

from toporia_core.framework import Solver
from toporia_core.framework.problem.run import Output

from . import cantilever_3d

NAME = "Cantilever 3D (Truss)"
ORDER = 31
ABOUT = "The 3-D cantilever found as a space truss on a ground structure, made into an STL solid at the end."
REFERENCE = ('W. S. Dorn, R. E. Gomory, H. J. Greenberg, "Automatic design of optimal structures", J. Mécanique'
             " 3 (1964) 25-52. Papers: https://doi.org/10.1007/978-3-662-05086-6")


def scenario():
    """The 3-D cantilever's physical problem, unchanged."""
    return cantilever_3d.scenario()


def solver() -> Solver:
    """The truss method in 3-D on a 5 mm ground structure."""
    return Solver(method="truss", method_params={"spacing": 5.0, "reach": 2},
                  filter_specs=[], m=0.4, max_iter=150, tol=1e-3)


def output() -> Output:
    """At the end: the bars as one STL surface."""
    return Output(postprocess=[{"type": "truss_solid"}])


def _description():
    from ._truss_description import truss_description
    return truss_description(__import__(__name__, fromlist=["x"]),
                             "the post-processor truss_solid joins the rods into one STL surface with balls at the "
                             "joints, traced from their signed distance field by marching cubes.")
