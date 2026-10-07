# plugins/filters/density.py — DensityFilter (spatial averaging filter)
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

from toporia.framework.parts.filter import Filter
from toporia.plugins.shared_params import RMIN

from ._neighbours import neighbour_matrix


class DensityFilter(Filter):
    """Weighted-average spatial filter (linear density filter).

    rmin: filter radius in elements.
    """

    name = "density"
    label = "Density filter"
    dims = (2, 3)
    order = 10
    params = (RMIN,)

    def __init__(self, rmin=1.5):
        self.rmin = rmin

    def setup(self, problem, solver):
        rmin        = self.rmin
        if getattr(problem, "dims", 2) == 3:
            # 3-D: the same weights in any dimension, elements in C order.
            self._shape, self._order = problem.shape, "C"
            self.H, self.Hs = neighbour_matrix(problem.shape, rmin)
            return
        nely, nelx  = problem.nely, problem.nelx
        self._shape, self._order = (nely, nelx), "F"
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
        order = self._order
        return (self.H @ x.reshape(-1, order=order) / self.Hs).reshape(self._shape, order=order)

    def backward(self, x_in, sensitivity):
        order = self._order
        return (self.H @ (sensitivity.reshape(-1, order=order) / self.Hs)).reshape(self._shape, order=order)
