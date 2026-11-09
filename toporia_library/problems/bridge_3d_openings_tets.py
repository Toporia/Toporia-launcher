# toporia_library/problems/bridge_3d_openings_tets.py — a 3-D bridge deck with two round openings, on tetrahedra.
#
# A 80 x 20 x 8 mm block supported at both bottom ends (one pinned, one on a roller) and
# loaded downward along the top middle, with two round openings of radius 5 mm through its
# depth at a quarter and three quarters of the span.  The mesh follows the openings, so the
# arches the optimiser builds around them meet round boundaries.  Exported as an STL.
# A demonstration of 3-D unstructured meshes (Wave 5).

from toporia_core.framework import (
    HoleConfig,
    LoadCase,
    PointConstraint,
    PointLoad,
    Scenario,
    Solver,
)
from toporia_core.framework.problem.run import Output

NAME = "Bridge 3D with Round Openings (Tetrahedra)"
ORDER = 33
ABOUT = ("A 3-D bridge block with two round openings through its depth, supported at both ends and loaded at the"
         " middle of the deck, optimised on tetrahedra that follow the openings.")
REFERENCE = "Demonstration preset of Toporia's tetrahedral meshes; geometry chosen here."


def scenario() -> Scenario:
    """An 80 x 20 x 8 mm block, two bores of radius 5 mm, supports at the bottom ends, a load at the top middle."""
    Lx, Ly, Lz = 80.0, 20.0, 8.0
    return Scenario(
        Lx=Lx, Ly=Ly, Lz=Lz,
        holes=[HoleConfig(cx=20.0, cy=8.0, r_void=5.0, r_passive=5.0),
               HoleConfig(cx=60.0, cy=8.0, r_void=5.0, r_passive=5.0)],
        point_constraints=[PointConstraint(x=0.0, y=0.0, dof="both"), PointConstraint(x=Lx, y=0.0, dof="y")],
        point_loads=[PointLoad(x=Lx / 2, y=Ly)],
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],
        volfrac=0.3,
    )


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
