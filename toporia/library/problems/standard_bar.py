# standard_bar.py - simple rectangular bar benchmark
#
# Coordinate convention:
#   (0,  Ly) ---------------------- (Lx, Ly)
#      |                              |
#      |                              |
#   (0,   0) ---------------------- (Lx,  0)
#   fixed left edge                    load point
#
# The xy origin is the bottom-left corner. This matches the live canvas and
# saved density PNGs, which display row 0 of the density array at the bottom.

from toporia.core import EdgeConstraint, LoadCase, PointLoad, Scenario

NAME = "Standard Bar"
ORDER = 40


def scenario() -> Scenario:
    Lx, Ly = 60.0, 20.0
    return Scenario(
        Lx=Lx,
        Ly=Ly,
        edge_constraints=[
            EdgeConstraint(edge="left", dof="both"),
        ],
        point_loads=[
            PointLoad(x=Lx, y=0.0),
        ],
        # PointLoad defines where the force acts; LoadCase defines direction.
        # Fa=270 degrees is a downward force at the bottom-right corner.
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],
        volfrac=0.5,
    )
