# filter_symmetry.py - SymmetryFilter (mirror-average density constraint)
#
# Enforces geometric symmetry by replacing the incoming density field with the
# average of itself and its mirrored copy. The operation is linear and
# self-adjoint, so the backward pass is the same averaging operation.

from toporia.core.params import Param

from .filter_base import Filter


class SymmetryFilter(Filter):
    """Mirror-average density filter.

    Parameters
    ----------
    axis : str
        "left_right" mirrors across the vertical centerline.
        "bottom_top" mirrors across the horizontal centerline.
        "both" applies both symmetry operations.
    """

    _ALIASES = {
        "lr": "left_right",
        "left-right": "left_right",
        "left_right": "left_right",
        "horizontal": "left_right",
        "bt": "bottom_top",
        "bottom-top": "bottom_top",
        "bottom_top": "bottom_top",
        "vertical": "bottom_top",
        "both": "both",
    }

    name = "symmetry"
    label = "Symmetry filter"
    order = 60
    params = (
        Param("axis", "left_right", "Axis", "Mirror-average the density field around this centreline.",
              choices=(("left_right", "Left-right"), ("bottom_top", "Bottom-top"), ("both", "Both"))),
    )

    def __init__(self, axis="left_right"):
        key = str(axis).strip().lower()
        if key not in self._ALIASES:
            raise ValueError(
                "axis must be 'left_right', 'bottom_top', or 'both' "
                f"- got {axis!r}"
            )
        self.axis = self._ALIASES[key]

    def setup(self, problem, solver):
        pass

    def _apply_once(self, x, axis):
        if axis == "left_right":
            return 0.5 * (x + x[:, ::-1])
        if axis == "bottom_top":
            return 0.5 * (x + x[::-1, :])
        raise ValueError(f"Unknown symmetry axis {axis!r}")

    def _apply(self, x):
        if self.axis == "both":
            return self._apply_once(self._apply_once(x, "left_right"), "bottom_top")
        return self._apply_once(x, self.axis)

    def forward(self, x):
        return self._apply(x)

    def backward(self, x_in, sensitivity):
        return self._apply(sensitivity)
