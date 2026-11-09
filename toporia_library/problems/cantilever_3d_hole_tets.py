# toporia_library/problems/cantilever_3d_hole_tets.py — the 3-D cantilever with a round hole, on tetrahedra.
#
# The 3-D cantilever (60 x 20 x 10 mm, clamped at x = 0, a downward line load at the far
# bottom edge) with a round hole of radius 4 mm through its depth at x = 20 mm, solved on a
# tetrahedral mesh fitted to the hole (toporia_library/physics/tet_mesh.py): the bore stays round
# instead of becoming a stack of cubes.  The fitted boundary is exported as an STL at the end.
# A demonstration of 3-D unstructured meshes (Wave 5).

from dataclasses import replace

from toporia_core.framework import HoleConfig, Solver
from toporia_core.framework.problem.run import Output

from . import cantilever_3d

NAME = "Cantilever 3D with a Hole (Tetrahedra)"
ORDER = 32
ABOUT = ("The 3-D cantilever with a round bore through its depth, optimised on tetrahedra that follow the bore"
         " instead of a stack of cubes.")
REFERENCE = ("The 3-D cantilever of top3d (K. Liu, A. Tovar, Struct. Multidisc. Optim. 50 (2014) 1175-1196) with a"
             " bore added here, on a body-fitted tetrahedral mesh. Papers: https://doi.org/10.1007/s00158-014-1107-x")


def scenario():
    """The 3-D cantilever with a bore of radius 4 mm through its depth at x = 20 mm."""
    return replace(cantilever_3d.scenario(), holes=[HoleConfig(cx=20.0, cy=10.0, r_void=4.0, r_passive=4.0)])


def solver() -> Solver:
    """Density on tetrahedra (2 mm cubes split in six), a 4 mm filter, SIMP p = 3, OC."""
    return Solver(method="unstructured", method_params={"element_size": 2.0, "rmin": 4.0},
                  filter_specs=[], m=0.4, max_iter=150, tol=0.01)


def output() -> Output:
    """At the end: the fitted boundary as an STL."""
    return Output(postprocess=[{"type": "mesh_surface"}])


def _description():
    from ._unstructured_description import unstructured_description
    return unstructured_description(__import__(__name__, fromlist=["x"]))
