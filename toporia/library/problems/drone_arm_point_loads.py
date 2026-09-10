# drone_arm_point_loads.py - drone arm geometry using point constraints/loads
#
# This mirrors the original drone arm coordinate layout, but does not prescribe
# any void holes or passive solid rings. The frame mounts are point constraints,
# and the motor mount locations are point loads.
#
# Coordinate convention:
#   xy origin is the bottom-left corner, matching the displayed density fields.

from toporia.core import LoadCase, PointConstraint, PointLoad, Scenario

NAME = "Drone Arm (Point Loads)"
ORDER = 70


def scenario() -> Scenario:
    return Scenario(
        Lx=200.0,
        Ly=85.0,
        point_constraints=[
            PointConstraint(x=85.1,  y=75.0, dof="both"),
            PointConstraint(x=115.6, y=75.0, dof="both"),
        ],
        point_loads=[
            PointLoad(x=7.9,   y=17.6),
            PointLoad(x=15.2,  y=8.9),
            PointLoad(x=16.6,  y=24.9),
            PointLoad(x=23.8,  y=16.2),
            PointLoad(x=192.8, y=17.6),
            PointLoad(x=185.6, y=8.9),
            PointLoad(x=184.2, y=24.9),
            PointLoad(x=176.9, y=16.2),
        ],
        # PointLoad defines where the forces act; LoadCase defines direction.
        # Equal +x and +y load cases are combined with equal weights.
        load_cases=[
            LoadCase(Fmag=1.0, Fa=0.0,  weight=0.5),
            LoadCase(Fmag=1.0, Fa=90.0, weight=0.5),
        ],
        volfrac=0.5,
    )
