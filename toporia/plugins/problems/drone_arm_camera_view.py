# drone_arm_camera_view.py - drone arm with an enforced empty camera-view area
#
# This starts from the regular drone arm setup and adds a symmetric empty
# polygon near the bottom center, representing the camera view that should stay
# unobstructed.
#
# Coordinate convention:
#   xy origin is the bottom-left corner, matching the displayed density fields.

from dataclasses import replace

from toporia.framework import EnforcedArea, Scenario

from . import drone_arm

NAME = "Drone Arm (Camera View)"
ORDER = 60


def scenario() -> Scenario:
    """The physical problem: domain, supports, loads, material, volume budget."""
    base = drone_arm.scenario()

    # Symmetric about x=100. The sketch shows a wide lower opening with a
    # slightly narrower upper edge under the central body.
    camera_view = EnforcedArea(
        points=[
            (55.0, 0.0),
            (145.0, 0.0),
            (133.0, 34.0),
            (67.0, 34.0),
        ],
        kind="empty",
    )
    return replace(base, enforced_areas=[*base.enforced_areas, camera_view])
