# filter_milling.py — MillingFilter (CNC milling accessibility constraint)
#
# For each tool direction, computes a running L_P-maximum of densities from the
# entry face inward.  The running max ensures that once solid material appears in
# a column/row it persists all the way to the entry face — a void "underneath"
# solid (from the tool's perspective) is filled in, making the design reachable.
#
#   xf_d[i] ≈ max(x[0], x[1], …, x[i])   propagated from the entry face
#
# Multiple directions are combined with a soft minimum (negative-P KS aggregation),
# so the physical density is the minimum of what is accessible from each direction.
# This enforces that the element is reachable from ALL specified tool directions.
#
# Direction IDs in IMAGE coordinates (canvas.py applies np.flipud, so
# array row 0 is at the IMAGE BOTTOM, array row nely-1 is at the IMAGE TOP):
#   0 = tool enters from IMAGE BOTTOM  (array row 0),      propagates UP ↑ in image
#   1 = tool enters from IMAGE LEFT    (array col 0),      propagates RIGHT →
#   2 = tool enters from IMAGE TOP     (array row nely-1), propagates DOWN ↓ in image
#   3 = tool enters from IMAGE RIGHT   (array col nelx-1), propagates LEFT ←
#
# Backward pass:
#   Adjoint of the running L_P-max followed by adjoint of the KS-min combination.

import numpy as np
from .filter_base import Filter


class MillingFilter(Filter):
    """CNC milling accessibility filter.

    Parameters
    ----------
    directions : list of int in {0,1,2,3} — tool entry faces to constrain.
                 0=top, 1=left, 2=bottom, 3=right (image coordinates).
    P          : L_P / KS sharpness.  Larger values approach hard max/min.
                 Recommended ≥ 10; too large can cause numerical issues.
    """

    def __init__(self, directions=None, P=20):
        self.directions = list(directions) if directions is not None else [0]
        self.P          = float(P)
        self._xfs       = []

    def setup(self, problem, config):
        self._shape = (problem.nely, problem.nelx)
        # Passive elements are forced to x=1.0 by _physical_density.  If left at 1.0
        # they inflate the running max to 1.0 for every element downstream of the bolt
        # rings, making sum(x_phys) >> volfrac, collapsing OC to near-zero densities,
        # and causing FEA to fail on the next iteration.  Masking them to 0 means only
        # designable density propagates.
        self._passive_mask = getattr(problem, 'passive_elements',
                                     np.zeros(self._shape, dtype=bool))

    # ── L_P running maximum (forward + adjoint) ──────────────────────────────

    def _lp_forward(self, x, direction):
        """Running L_P maximum from the entry face toward the opposite face."""
        P    = self.P
        eps  = 1e-300   # prevent 0**negative
        nely, nelx = self._shape
        xf   = x.copy()

        if direction == 0:          # entry: image bottom (array row 0) → propagates up
            for i in range(1, nely):
                a, b      = np.maximum(x[i, :], 0.0), np.maximum(xf[i - 1, :], 0.0)
                xf[i, :]  = (a ** P + b ** P + eps) ** (1.0 / P)
        elif direction == 1:        # entry: image left (array col 0) → propagates right
            for j in range(1, nelx):
                a, b      = np.maximum(x[:, j], 0.0), np.maximum(xf[:, j - 1], 0.0)
                xf[:, j]  = (a ** P + b ** P + eps) ** (1.0 / P)
        elif direction == 2:        # entry: image top (array row nely-1) → propagates down
            for i in range(nely - 2, -1, -1):
                a, b      = np.maximum(x[i, :], 0.0), np.maximum(xf[i + 1, :], 0.0)
                xf[i, :]  = (a ** P + b ** P + eps) ** (1.0 / P)
        elif direction == 3:        # entry: image right (array col nelx-1) → propagates left
            for j in range(nelx - 2, -1, -1):
                a, b      = np.maximum(x[:, j], 0.0), np.maximum(xf[:, j + 1], 0.0)
                xf[:, j]  = (a ** P + b ** P + eps) ** (1.0 / P)
        return xf

    def _lp_backward(self, x, xf, sensitivity, direction):
        """Adjoint of the L_P running maximum.

        d/dx_i  of  xf_i = (x_i^P + xf_{i-1}^P)^(1/P)
            w.r.t. x_i   is  x_i^(P-1) / xf_i^(P-1)
            w.r.t. xf_{i-1} is  xf_{i-1}^(P-1) / xf_i^(P-1)
        Propagate sensitivity in reverse order, accumulating upstream contributions.
        """
        P    = self.P
        eps  = 1e-300
        nely, nelx = self._shape
        s  = sensitivity.copy()   # accumulates the backpropagated gradient
        sx = np.zeros_like(x)

        if direction == 0:
            for i in range(nely - 1, -1, -1):
                if i == 0:
                    sx[i, :] = s[i, :]
                else:
                    a, b      = np.maximum(x[i, :], 0.0), np.maximum(xf[i - 1, :], 0.0)
                    total     = a ** P + b ** P + eps
                    coeff     = total ** ((1.0 / P) - 1.0)
                    sx[i, :]   = s[i, :] * a ** (P - 1.0) * coeff
                    s[i - 1, :] += s[i, :] * b ** (P - 1.0) * coeff
        elif direction == 1:
            for j in range(nelx - 1, -1, -1):
                if j == 0:
                    sx[:, j] = s[:, j]
                else:
                    a, b      = np.maximum(x[:, j], 0.0), np.maximum(xf[:, j - 1], 0.0)
                    total     = a ** P + b ** P + eps
                    coeff     = total ** ((1.0 / P) - 1.0)
                    sx[:, j]     = s[:, j] * a ** (P - 1.0) * coeff
                    s[:, j - 1] += s[:, j] * b ** (P - 1.0) * coeff
        elif direction == 2:
            for i in range(nely):
                if i == nely - 1:
                    sx[i, :] = s[i, :]
                else:
                    a, b      = np.maximum(x[i, :], 0.0), np.maximum(xf[i + 1, :], 0.0)
                    total     = a ** P + b ** P + eps
                    coeff     = total ** ((1.0 / P) - 1.0)
                    sx[i, :]    = s[i, :] * a ** (P - 1.0) * coeff
                    s[i + 1, :] += s[i, :] * b ** (P - 1.0) * coeff
        elif direction == 3:
            for j in range(nelx):
                if j == nelx - 1:
                    sx[:, j] = s[:, j]
                else:
                    a, b      = np.maximum(x[:, j], 0.0), np.maximum(xf[:, j + 1], 0.0)
                    total     = a ** P + b ** P + eps
                    coeff     = total ** ((1.0 / P) - 1.0)
                    sx[:, j]     = s[:, j] * a ** (P - 1.0) * coeff
                    s[:, j + 1] += s[:, j] * b ** (P - 1.0) * coeff
        return sx

    # ── Filter interface ──────────────────────────────────────────────────────

    def forward(self, x):
        """Apply running max per direction, then combine with soft minimum.
        Returns x unchanged if no directions are selected (no constraint applied).
        """
        if not self.directions:
            return x.copy()
        # Zero passive elements so their forced x=1 doesn't inflate the running max
        # for the entire downstream domain.
        x_eff = x.copy()
        x_eff[self._passive_mask] = 0.0
        self._x_eff = x_eff   # saved for use in backward

        P_ks = -self.P          # negative → KS minimum
        N    = len(self.directions)
        self._xfs = []
        KS = np.zeros_like(x)
        for d in self.directions:
            xf = self._lp_forward(x_eff, d)
            self._xfs.append(xf)
            KS += np.exp(np.clip(P_ks * xf, -500.0, 0.0))
        return np.log(KS / N) / P_ks

    def backward(self, x_in, sensitivity):
        """Chain rule: adjoint of KS-min then adjoint of each running max."""
        if not self.directions:
            return sensitivity.copy()
        P_ks = -self.P
        N    = len(self.directions)
        # Recompute KS using the stored xf arrays from the last forward pass.
        KS = np.zeros_like(x_in)
        for xf in self._xfs:
            KS += np.exp(np.clip(P_ks * xf, -500.0, 0.0))

        ds_dx = np.zeros_like(x_in)
        for d, xf in zip(self.directions, self._xfs):
            # Use self._x_eff (passive-masked) to match the forward computation.
            dout_dxf = np.exp(np.clip(P_ks * xf, -500.0, 0.0)) / KS
            ds_dx   += self._lp_backward(self._x_eff, xf, sensitivity * dout_dxf, d)
        return ds_dx
