# plugins/problems/michell_cantilever.py — a point load carried to a circular support.
#
# Michell (1904) found the stiffest frame that carries a point load to a rigid
# circular support: two families of orthogonal spirals (equiangular spirals
# leaving the circle at 45°) meeting at the load.  It is one of the very few
# topology-optimisation problems whose optimal layout is known analytically,
# which makes it the natural check that a method converges to the right
# *shape*, not only to a low number.
#
#   (0, Ly) ───────────────────────────────── (Lx, Ly)
#      |                                          |
#      |    ( O )  clamped ring                   ↓ F at (Lx, Ly/2)
#      |                                          |
#   (0,  0) ───────────────────────────────── (Lx,  0)
#
# The continuum version here is the usual one: the support is a clamped ring
# around a hole, the load acts at mid-height on the right edge, and the volume
# fraction is low, so the design is a frame of thin members.  The analytical
# optimum is a truss of infinitely many members; a continuum design at finite
# resolution approaches it, so compare layouts, not exact numbers.
#
# Reference: A. G. M. Michell, "The limits of economy of material in
# frame-structures", Philosophical Magazine 8 (1904) 589–597.

from toporia.framework import HoleConfig, LoadCase, PointLoad, Scenario, Solver

NAME = "Michell Cantilever"
ORDER = 25


def scenario() -> Scenario:
    """The physical problem: domain, supports, loads, material, volume budget."""
    Lx, Ly = 100.0, 60.0
    return Scenario(
        Lx=Lx,
        Ly=Ly,
        holes=[
            # The rigid circular support: a void core inside a clamped solid ring.
            HoleConfig(cx=20.0, cy=Ly / 2.0, r_void=6.0, r_passive=9.0, kind="fixed"),
        ],
        point_loads=[PointLoad(x=Lx, y=Ly / 2.0)],
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],   # downward
        volfrac=0.2,
    )


def solver() -> Solver:
    """The solver settings recommended for this problem."""
    # A low volume fraction makes thin members, so a little more iteration room.
    return Solver(method="q4+oc", filter_specs=[{"type": "density"}], m=1.0, max_iter=150, tol=0.01)
