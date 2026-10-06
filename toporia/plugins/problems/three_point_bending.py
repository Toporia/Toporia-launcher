# three_point_bending.py - simple three-point bending test setup
#
# Coordinate convention:
#   (0,  Ly) ---------- load ---------- (Lx, Ly)
#      |                  v              |
#      |                                 |
#   (0,   0) -------------------------- (Lx,  0)
#   pinned support                     roller support
#
# The xy origin is the bottom-left corner. This matches the live canvas and
# saved density PNGs, which display row 0 of the density array at the bottom.

from toporia.framework import LoadCase, PointConstraint, PointLoad, Scenario

NAME = "Three-Point Bending"
ORDER = 30


def scenario() -> Scenario:
    """The physical problem: domain, supports, loads, material, volume budget."""
    Lx, Ly = 60.0, 20.0
    return Scenario(
        Lx=Lx,
        Ly=Ly,
        point_constraints=[
            PointConstraint(x=0.0, y=0.0, dof="both"),
            PointConstraint(x=Lx, y=0.0, dof="y"),
        ],
        point_loads=[
            PointLoad(x=Lx / 2.0, y=Ly),
        ],
        # PointLoad defines where the force acts; LoadCase defines direction.
        # Fa=270 degrees is a downward force at the top-center load point.
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],
        volfrac=0.5,
    )
