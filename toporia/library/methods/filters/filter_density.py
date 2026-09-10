# filter_density.py — DensityFilter (spatial averaging filter)
#
# Weighted-average filter over a circular neighbourhood of radius rmin.
# Enforces a minimum length scale and prevents checkerboard patterns.
#
# Physical density:  x_phys = H @ x / Hs
# Adjoint (backward): ds/dx  = H @ (ds/dx_phys / Hs)
#
# H is symmetric, so the adjoint equals the forward operator (up to 1/Hs scaling).

import numpy as np
from scipy.sparse import coo_matrix

from toporia.core.params import Param

from .filter_base import Filter

# Shared by the sensitivity filter and the pyMOTO method, which apply the same
# neighbourhood radius and should present it identically.
RMIN = Param(
    "rmin", 1.5, "Radius",
    "Filter radius in elements. Sets the minimum member size and suppresses checkerboarding.",
    min=0.5, max=20.0, step=0.5, decimals=2, units="el",
)


class DensityFilter(Filter):
    """Weighted-average spatial filter (linear density filter).

    rmin: filter radius in elements.
    """

    name = "density"
    label = "Density filter"
    order = 10
    params = (RMIN,)

    def __init__(self, rmin=1.5):
        self.rmin = rmin

    def setup(self, problem, solver):
        rmin        = self.rmin
        nely, nelx  = problem.nely, problem.nelx
        self._shape = (nely, nelx)
        reach       = int(np.ceil(rmin) - 1)

        rows, cols, vals = [], [], []
        for i in range(nelx):
            for j in range(nely):
                row = i * nely + j
                for k in range(max(i - reach, 0), min(i + reach + 1, nelx)):
                    for l in range(max(j - reach, 0), min(j + reach + 1, nely)):
                        w = max(0.0, rmin - np.sqrt((i - k) ** 2 + (j - l) ** 2))
                        if w > 0.0:
                            rows.append(row)
                            cols.append(k * nely + l)
                            vals.append(w)

        n       = nelx * nely
        self.H  = coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsr()
        self.Hs = np.asarray(self.H.sum(axis=1)).ravel()

    def forward(self, x):
        nely, nelx = self._shape
        return (self.H @ x.reshape(-1, order="F") / self.Hs).reshape(
            (nely, nelx), order="F"
        )

    def backward(self, x_in, sensitivity):
        nely, nelx = self._shape
        return (self.H @ (sensitivity.reshape(-1, order="F") / self.Hs)).reshape(
            (nely, nelx), order="F"
        )
