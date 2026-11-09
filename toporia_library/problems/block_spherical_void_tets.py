# toporia_library/problems/block_spherical_void_tets.py — a 3-D block around a spherical void, on tetrahedra.
#
# A 40 x 20 x 20 mm cantilever block clamped at x = 0 and loaded downward along its far top
# edge, with a spherical void of diameter 10 mm at its centre (a space that must stay empty,
# e.g. for a part passing through).  The tetrahedral mesh is snapped onto the sphere, so the
# design wraps a round cavity.  The problem is written as explicit objects (the Problem
# editor's form), so it opens editable.  A demonstration of 3-D unstructured meshes (Wave 5).

from toporia_core.framework import LoadCase, Scenario, Solver
from toporia_core.framework.problem.run import Output

NAME = "Block around a Spherical Void (Tetrahedra)"
ORDER = 34
ABOUT = ("A 3-D cantilever block that must leave a spherical cavity empty, optimised on tetrahedra snapped onto"
         " the sphere.")
REFERENCE = "Demonstration preset of Toporia's tetrahedral meshes; geometry chosen here."


def _object(identity, shape, position, size, role, **values):
    return {"id": identity, "name": identity.replace("-", " ").title(), "shape": shape, "position": list(position),
            "size": list(size), "rotation": [0.0, 0.0, 0.0], "role": role, "axes": ["x", "y", "z"],
            "force": [0.0, -1.0, 0.0], "case": 0, **values}


def scenario() -> Scenario:
    """A 40 x 20 x 20 mm block, clamped face, line load at the far top edge, a sphere of 10 mm left empty."""
    Lx, Ly, Lz = 40.0, 20.0, 20.0
    return Scenario(
        Lx=Lx, Ly=Ly, Lz=Lz, volfrac=0.25, load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],
        regions=[
            _object("clamped-face", "box", (0.0, 0.0, 0.0), (0.0, Ly, Lz), "support"),
            _object("edge-load", "line", (Lx, Ly, 0.0), (0.0, 0.0, Lz), "load"),
            _object("spherical-void", "sphere", (Lx / 2, Ly / 2, Lz / 2), (10.0, 10.0, 10.0), "void"),
        ])


def solver() -> Solver:
    """Density on tetrahedra (2 mm cubes split in six), a 4 mm filter, SIMP p = 3, OC."""
    return Solver(method="unstructured", method_params={"element_size": 2.0, "rmin": 4.0},
                  filter_specs=[], m=0.5, max_iter=150, tol=0.01)


def output() -> Output:
    """At the end: the fitted boundary as an STL."""
    return Output(postprocess=[{"type": "mesh_surface"}])


def _description():
    from ._unstructured_description import unstructured_description
    return unstructured_description(__import__(__name__, fromlist=["x"]))
