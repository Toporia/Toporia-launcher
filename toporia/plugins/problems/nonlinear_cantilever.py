# nonlinear_cantilever.py — a cantilever whose tip load is large enough to bend it visibly.
#
# The geometry of the Cantilever preset (clamped left edge, point load at mid-height of the
# free end, 60 × 30, 40 % material) but with the load chosen for the material (E0 = 1) so that
# the uniform beam's tip moves by a good fraction of the beam depth and the lever arm shortens
# as it bends.  The linear theory ignores that; the non-linear solve (q4_nonlinear) follows it
# and designs for the stiffness the structure has when loaded (Buhl, Pedersen & Sigmund 2000).
# Much larger loads make the early grey designs of the optimiser snap or buckle, which load
# control cannot follow (the solve then stops with an error naming the load fraction).
#
#   (0, Ly) ────────────────────────── (Lx, Ly)
#      |||                                  |
#      |||       [material domain]          v  F, large
#      |||                                  |
#   (0,  0) ────────────────────────── (Lx,  0)

from toporia.framework import EdgeConstraint, EnforcedArea, LoadCase, PointLoad, Scenario, Solver

NAME = "Nonlinear Cantilever"
ORDER = 25
ABOUT = ('A cantilever with a large tip load, designed with geometrically non-linear elasticity (large'
         ' displacements, Newton–Raphson with load steps) so the design accounts for how the beam bends.')
REFERENCE = ('Stiffness design of geometrically non-linear structures, T. Buhl, C. B. W. Pedersen, O. Sigmund,'
             ' Struct. Multidisc. Optim. 19 (2000) 93-104; void by energy interpolation after Wang, Lazarov,'
             ' Sigmund & Jensen, CMAME 276 (2014) 453-472.'
             ' Papers: https://doi.org/10.1007/s001580050089 https://doi.org/10.1016/j.cma.2014.03.021')


def scenario() -> Scenario:
    """The physical problem: the cantilever, with a tip load large enough to need the non-linear solve."""
    Lx, Ly = 60.0, 30.0
    return Scenario(
        Lx=Lx,
        Ly=Ly,
        edge_constraints=[EdgeConstraint(edge="left", dof="both")],
        point_loads=[PointLoad(x=Lx, y=Ly / 2.0)],
        # Downward. 0.03 is about 4 % off the linear end compliance for the uniform start design.
        load_cases=[LoadCase(Fmag=0.03, Fa=270.0, weight=1.0)],
        # A solid pad where the point load acts, as Buhl et al. use: a force on a single node of a soft
        # element would crush it and the solve would have nothing to follow.
        enforced_areas=[EnforcedArea(points=[(Lx - 6.0, Ly / 2.0 - 4.0), (Lx, Ly / 2.0 - 4.0),
                                             (Lx, Ly / 2.0 + 4.0), (Lx - 6.0, Ly / 2.0 + 4.0)], kind="full")],
        volfrac=0.4,
        objective={"type": "end_compliance"},
    )


def solver() -> Solver:
    """MMA on the non-linear model: a coarse mesh keeps a run to a few minutes."""
    return Solver(method="q4_nonlinear+mma", filter_specs=[{"type": "density"}], m=0.5, max_iter=60, tol=0.01)
