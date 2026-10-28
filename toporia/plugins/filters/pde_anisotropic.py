"""Axis-aligned anisotropic Helmholtz filtering on cell-centred densities.

Directional extension of Lazarov & Sigmund, IJNME 86 (2011) 765-781,
https://doi.org/10.1002/nme.3072. This is Toporia's finite-volume discretisation,
not a port of top82.m's nodal finite elements.

In mesh coordinates, -div(D grad(rho_bar)) + rho_bar = rho, with zero boundary
flux and D = diag(rmin_x**2, rmin_y**2, rmin_z**2) / 12. A zero radius removes
diffusion along that axis. The uniform-cell volume cancels from the equations.

A = I + sum_a D_aa L_a is symmetric positive definite, has row sums one and
non-positive off-diagonals. Its inverse is non-negative and doubly stochastic:
the filter preserves density bounds, constants and volume, even for very
different radii. One sparse factorisation serves forward and exact adjoint.
"""

import numpy as np
from scipy.sparse import csc_matrix, diags, eye
from scipy.sparse.linalg import splu

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter

from .pde import _chain


def _neumann_laplacian(n):
    """Finite-volume -d²/dx² on n unit cells, with no flux at the two ends."""
    if n == 1:
        return csc_matrix((1, 1))
    diagonal = np.full(n, 2.0)
    diagonal[[0, -1]] = 1.0
    return diags([-np.ones(n - 1), diagonal, -np.ones(n - 1)], [-1, 0, 1], format="csc")


class AnisotropicPdeFilter(Filter):
    """Helmholtz smoothing with independent x/y/z radii, measured in elements."""

    name = "pde_anisotropic"
    label = "Anisotropic PDE (Helmholtz) filter"
    use_when = (
        "When features should be longer in one grid direction than another, e.g. fibre-like or layered "
        "parts. Directions follow the grid axes only."
    )
    reference = (
        'Directional extension of B. S. Lazarov and O. Sigmund, "Filters in topology '
        'optimization based on Helmholtz-type differential equations", Int. J. Numer. '
        'Meth. Eng. 86 (2011) 765-781. Toporia uses conservative cell-centred finite '
        'volumes and an axis-aligned diagonal diffusion tensor.'
        ' Papers: https://doi.org/10.1002/nme.3072'
    )
    order = 12
    dims = (2, 3)
    params = (
        Param("rmin_x", 3.0, "Radius along x",
              "Equivalent density-filter radius in x, in elements; 0 leaves this direction unsmoothed.",
              min=0.0, max=100.0, step=0.1, decimals=2, units="el"),
        Param("rmin_y", 1.5, "Radius along y",
              "Equivalent density-filter radius in y, in elements; 0 leaves this direction unsmoothed.",
              min=0.0, max=100.0, step=0.1, decimals=2, units="el"),
        Param("rmin_z", 1.5, "Radius along z (3-D)",
              "Equivalent density-filter radius in z, in elements; used only on 3-D grids.",
              min=0.0, max=100.0, step=0.1, decimals=2, units="el"),
    )

    def __init__(self, rmin_x=3.0, rmin_y=1.5, rmin_z=1.5):
        radii = np.asarray((rmin_z, rmin_y, rmin_x), dtype=float)
        if np.any(~np.isfinite(radii)) or np.any(radii < 0):
            raise ValueError("Anisotropic PDE radii must be finite and non-negative")
        self.radii = radii

    def setup(self, problem, solver):
        self._shape = tuple(problem.shape)  # (y, x) or (z, y, x), C-order
        identities = [eye(n, format="csc") for n in self._shape]
        matrix = eye(int(np.prod(self._shape)), format="csc")
        for axis, radius in enumerate(self.radii[-len(self._shape):]):
            if radius == 0:
                continue
            factors = list(identities)
            factors[axis] = _neumann_laplacian(self._shape[axis])
            matrix = matrix + (radius ** 2 / 12.0) * _chain(factors)
        self._lu = splu(csc_matrix(matrix))

    def forward(self, x):
        return self._lu.solve(np.asarray(x, dtype=float).reshape(-1)).reshape(self._shape)

    def backward(self, x_in, sensitivity):
        # A is symmetric; this is the exact derivative transpose, without clipping.
        return self.forward(sensitivity)
