# drone_arm_camera_view.py - drone arm with an enforced empty camera-view area
#
# This starts from the regular drone arm setup and adds a symmetric empty
# polygon near the bottom center, representing the camera view that should stay
# unobstructed.
#
# Coordinate convention:
#   xy origin is the bottom-left corner, matching the displayed density fields.

from dataclasses import replace

from toporia.core.config import EnforcedArea, TopOptConfig
from .drone_arm import get_config as _get_drone_arm_config


def get_config() -> TopOptConfig:
    cfg = _get_drone_arm_config()

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

    return replace(cfg, enforced_areas=[*cfg.enforced_areas, camera_view])
