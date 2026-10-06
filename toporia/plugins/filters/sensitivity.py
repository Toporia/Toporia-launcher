# plugins/filters/sensitivity.py — SensitivityFilter (heuristic sensitivity filter)
#
# This implements the classic sensitivity-filter approach from the top88 MATLAB code:
#   - Physical density = design variable (no spatial smoothing of densities)
#   - Compliance sensitivity dc is averaged using a density-weighted scheme:
#       dc_new[e] = (H @ (x * dc) / Hs)[e] / max(x[e], 1e-3)
#   - Volume sensitivity dv is left unchanged (returns identity).
#
# The volume identity is why backward_volume() is overridden: it ensures the
# OC update uses dv=1 exactly, matching the original top88 behaviour.
#
# NOTE: this is a heuristic, not a proper chain-rule adjoint.  The density
# filter (density.py) with adjoint propagation is recommended for new work.

import numpy as np
from scipy.sparse import coo_matrix

from toporia.framework.parts.filter import Filter
from toporia.plugins.shared_params import RMIN


class SensitivityFilter(Filter):
    """Heuristic sensitivity-averaging filter.

    forward  — identity: x_phys = x
    backward — density-weighted neighbourhood average of dc
    backward_volume — identity: dv passes through unchanged
    """

    name = "sensitivity"
    label = "Sensitivity filter"
    order = 20
    params = (RMIN,)
    exact_adjoint = False   # a heuristic: backward() is not the derivative of forward()

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
        """Identity: physical density equals design variable."""
        return x.copy()

    def backward(self, x_in, sensitivity):
        """Density-weighted neighbourhood average (heuristic, not a true adjoint)."""
        nely, nelx = self._shape
        x_flat = x_in.reshape(-1, order="F")
        s_flat = sensitivity.reshape(-1, order="F")
        result = (self.H @ (x_flat * s_flat) / self.Hs) / np.maximum(1e-3, x_flat)
        return result.reshape((nely, nelx), order="F")

    def backward_volume(self, x_in, sensitivity):
        """Volume sensitivity is not filtered by this heuristic."""
        return sensitivity
