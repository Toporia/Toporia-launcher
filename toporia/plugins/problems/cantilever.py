# cantilever.py — cantilever beam benchmark
#
# A cantilever beam is the second most commonly cited benchmark in topology
# optimisation literature.  One end is fully clamped; a point load acts at
# the mid-height of the free end.
#
# Boundary conditions:
#
#   (0, Ly) ──────────────────────────── (Lx, Ly)
#      |||                                    |
#      |||       [material domain]             ← F (horizontal or at angle)
#      |||                                    |
#   (0,  0) ──────────────────────────── (Lx,  0)
#   fully clamped                         free end
#   (x=0 edge)                            mid-height load
#
# Coordinate convention — origin at the bottom-left corner:
#   (0, Ly) ─── top-left    (Lx, Ly) ─── top-right
#   (0,  0) ─── bottom-left (Lx,  0) ─── bottom-right

from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario

NAME = "Cantilever"
ORDER = 20


def scenario() -> Scenario:
    """The physical problem: domain, supports, loads, material, volume budget."""
    Lx, Ly = 60.0, 30.0   # 2:1 aspect ratio — common choice for cantilever
    return Scenario(
        Lx=Lx,
        Ly=Ly,
        edge_constraints=[
            # Left edge: both DOFs fixed — fully clamped wall.
            EdgeConstraint(edge="left", dof="both"),
        ],
        point_loads=[
            # Mid-height of the right (free) end.
            PointLoad(x=Lx, y=Ly / 2.0),
        ],
        # Fa=270° = downward force. Change to Fa=0° for a horizontal tip load.
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],
        volfrac=0.4,
    )
