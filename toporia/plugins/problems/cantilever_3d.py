# plugins/problems/cantilever_3d.py — the 3-D cantilever of Liu & Tovar's top3d, small enough to run in seconds.
#
#    clamped face (x = 0)                         free end
#    ┌──────────────────────────────────────────┐
#    │                                          │  20 mm high, 10 mm deep
#    │                                          │
#    └──────────────────────────────────────────┘ ↓ line load along the bottom
#                      60 mm                        edge of the free end, through the depth
#
# A 60 × 20 mm rectangle extruded 10 mm (framework/problem/mesh.py, BoxProblem),
# clamped over the whole face at x = 0 and loaded downward along the bottom
# edge of the free end, through the full depth — the benchmark of top3d.  At
# the recommended 0.4 elements per mm it has 24 × 8 × 4 = 768 bricks and runs
# 60 iterations of h8+oc in a few seconds; raise the resolution for a real
# design (1.0 el/mm is top3d's 60 × 20 × 10 mesh).
#
# Reference: K. Liu, A. Tovar, "An efficient 3D topology optimization code
# written in Matlab", Structural and Multidisciplinary Optimization 50 (2014)
# 1175-1196.

from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario, Solver

NAME = "Cantilever 3D"
ORDER = 22


def scenario() -> Scenario:
    """The physical problem: domain, supports, loads, material, volume budget."""
    Lx, Ly, Lz = 60.0, 20.0, 10.0
    return Scenario(
        Lx=Lx,
        Ly=Ly,
        Lz=Lz,
        edge_constraints=[EdgeConstraint(edge="left", dof="both")],    # the face x = 0, clamped
        point_loads=[PointLoad(x=Lx, y=0.0)],                          # a line through the depth
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],          # downward
        volfrac=0.3,
    )


def solver() -> Solver:
    """The solver settings recommended for this problem: small and quick."""
    return Solver(method="h8+oc", filter_specs=[{"type": "density", "rmin": 1.5}], m=0.4, max_iter=60, tol=0.01)
