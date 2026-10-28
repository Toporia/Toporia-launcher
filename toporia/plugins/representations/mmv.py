"""Restricted 2-D MMV: moving superelliptical holes in a solid domain.

The geometric dual of MMC: rho = product(1 - H(phi_i)). Holes can translate,
rotate, resize, intersect and merge. This own paper-based variant reuses MMC's
constant-thickness superellipse and exact Jacobian, with the sign reversed.
It does not implement the 2017 paper's B-spline surfaces or FE DOF removal.
The number of holes is fixed; new holes cannot nucleate during a run.
"""

import numpy as np

from toporia.framework.params import Param
from toporia.plugins.representations.mmc import MovingMorphableComponents


class MovingMorphableVoids(MovingMorphableComponents):
    """Five normalised variables per hole: centre, two half-axes and angle."""

    name = "mmv"
    label = "Moving morphable voids (2D)"
    use_when = (
        "When the design is a plate with a few explicit holes whose shape you want as parameters. 2-D "
        "only; use MMA-type updaters."
    )
    order = 25
    reference = (
        'W. Zhang et al., "Explicit three dimensional topology optimization via Moving '
        'Morphable Void (MMV) approach", CMAME 322 (2017) 590-614. '
        'Own restricted 2D superellipse variant. Papers: https://doi.org/10.1016/j.cma.2017.05.002'
    )
    advice = (
        "Use MMA or another general-vector updater, with method.move about 0.02. "
        "The fixed initial set of holes can grow and merge; it cannot nucleate new holes."
    )
    params = (
        Param("n_x", 4, "Holes across", "Initial number of holes across the domain.", min=1, max=20),
        Param("n_y", 2, "Holes down", "Initial number of holes down the domain.", min=1, max=20),
        Param("start_size", 0.35, "Initial half-size",
              "Initial half-axes as a fraction of each layout cell's width and height.",
              min=0.05, max=0.49, step=0.01, decimals=2),
        Param("edge_width", 1.0, "Edge width",
              "Smoothed hole boundary width in elements. Narrow edges need a finer mesh.",
              min=0.1, max=5.0, step=0.1, decimals=2, units="elements"),
    )

    def __init__(self, n_x=4, n_y=2, start_size=0.35, edge_width=1.0):
        if int(n_x) != n_x or int(n_y) != n_y or min(n_x, n_y) < 1:
            raise ValueError("n_x and n_y must be positive integers")
        if not np.isfinite(start_size) or not 0 < start_size < 0.5:
            raise ValueError("start_size must lie strictly between 0 and 0.5")
        if not np.isfinite(edge_width) or edge_width <= 0:
            raise ValueError("edge_width must be finite and positive")
        self.start_size = float(start_size)
        super().__init__(n_x=n_x, n_y=n_y, max_thickness=0.5, edge_width=edge_width)

    def setup(self, problem):
        # The shared kernel needs strictly positive physical ranges on tiny meshes.
        if min(problem.nelx, problem.nely) < 2:
            raise ValueError("MMV needs at least two elements across each domain direction")
        super().setup(problem)

    def _start_layout(self, Lx, Ly):
        width, height = Lx / self.n_x, Ly / self.n_y
        holes = np.array([
            [(i + 0.5) * width, (j + 0.5) * height,
             self.start_size * width, self.start_size * height, 0.0]
            for i in range(self.n_x) for j in range(self.n_y)
        ])
        return np.clip((holes - self.low) / self.span, 0.0, 1.0).reshape(-1)

    def density(self, z):
        return np.prod(1.0 - self._bars(np.asarray(z))["rho"], axis=0)

    def backward(self, z, sensitivity):
        # The shared kernel uses prefix/suffix products, never division by zero
        # when overlapping holes have a fully void interior.
        return -super().backward(np.asarray(z), sensitivity)
