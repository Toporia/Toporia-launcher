# filter_routing.py - RoutingRadiusFilter (2D router tool-radius constraint)
#
# Models a round 2D routing tool by applying a smooth morphological closing:
#
#   close(x) = erode(dilate(x))
#
# Dilation grows solid into nearby voids by the tool radius; erosion shrinks the
# result back. Thin void pockets/channels narrower than the tool diameter do not
# return after the shrink step. Thin solid ribs are intentionally not removed.
#
# The user-facing radius is in mm and is converted to element units with
# radius_el = radius_mm * config.m. The filter can be delayed/ramped in because
# applying manufacturing morphology from iteration 0 can collapse the early OC
# update before a load path has formed.
#
# threshold: elements with density below this value are treated as void (x=0)
# for the dilation step. This prevents scattered low-density artifacts from
# being treated as solid and inflating the closing result. The backward pass
# mirrors this — sub-threshold elements receive zero gradient from the routing
# path (their x^(P-1) term is zero), so they are never encouraged to grow via
# this filter.

import numpy as np

from toporia.core.params import Param

from .filter_base import Filter


class RoutingRadiusFilter(Filter):
    """2D routing tool-radius filter using smooth circular closing.

    Parameters
    ----------
    radius_mm : float
        Tool radius in physical millimetres. Converted to elements in setup().
    P : float
        Smooth max/min sharpness. Larger values approximate hard morphology.
    start_iter : int
        Iteration at which the routing filter starts blending in.
    ramp_iters : int
        Number of iterations used to ramp from identity to full routing.
    threshold : float
        Density threshold below which elements are treated as void (set to 0)
        before the dilation step. Prevents low-density scatter from growing.
    """

    name = "routing"
    label = "Routing radius filter"
    order = 50
    params = (
        Param("radius_mm", 2.0, "Radius", "Router tool radius.",
              min=0.0, max=100.0, step=0.5, decimals=2, units="mm"),
        Param("P", 20.0, "P (sharpness)", "Smooth max/min sharpness; larger approaches hard morphology.",
              min=1.0, max=200.0, step=5.0, decimals=0),
        Param("start_iter", 20, "Start iter", "Iteration at which the routing filter starts to take effect.",
              min=0, max=2000),
        Param("ramp_iters", 20, "Ramp iters", "Iterations used to blend from identity to full routing.",
              min=1, max=2000),
        Param("threshold", 0.05, "Threshold",
              "Density below which elements count as void for dilation, so low-density scatter cannot grow.",
              min=0.0, max=1.0, step=0.01, decimals=3),
    )

    def __init__(self, radius_mm=2.0, P=20, start_iter=20, ramp_iters=20, threshold=0.05):
        self.radius_mm = float(radius_mm)
        self.P = float(P)
        self.start_iter = int(start_iter)
        self.ramp_iters = max(1, int(ramp_iters))
        self._threshold = float(threshold)
        self._alpha = 0.0

    def setup(self, problem, config):
        self._shape = (problem.nely, problem.nelx)
        self.radius_el = max(0.0, self.radius_mm * float(config.m))
        self._offsets = self._make_offsets(self.radius_el)
        self._identity = self.radius_el <= 0.0 or len(self._offsets) <= 1
        self._alpha = 0.0 if self.start_iter > 0 else 1.0 / self.ramp_iters

        # Interior mask: 1 where the element is farther than radius_el from every
        # domain edge, 0 in the boundary band.  Elements in the boundary band can
        # be reached by a tool whose centre is outside the design space, so the
        # routing constraint does not bind there and the filter passes through.
        nely, nelx = self._shape
        ii = np.arange(nely, dtype=float)[:, None]
        jj = np.arange(nelx, dtype=float)[None, :]
        dist = np.minimum(
            np.minimum(ii, nely - 1 - ii),
            np.minimum(jj, nelx - 1 - jj),
        )
        self._interior_mask = (dist > self.radius_el).astype(float)

    def step(self, iteration):
        if iteration < self.start_iter:
            self._alpha = 0.0
        else:
            self._alpha = min(
                1.0, (iteration - self.start_iter + 1) / self.ramp_iters
            )

    @staticmethod
    def _make_offsets(radius):
        reach = int(np.ceil(radius))
        r2 = radius * radius
        offsets = []
        for di in range(-reach, reach + 1):
            for dj in range(-reach, reach + 1):
                if di * di + dj * dj <= r2 + 1e-12:
                    offsets.append((di, dj))
        return offsets

    def _slices(self, di, dj):
        nely, nelx = self._shape
        if di >= 0:
            out_i = slice(0, nely - di)
            in_i = slice(di, nely)
        else:
            out_i = slice(-di, nely)
            in_i = slice(0, nely + di)

        if dj >= 0:
            out_j = slice(0, nelx - dj)
            in_j = slice(dj, nelx)
        else:
            out_j = slice(-dj, nelx)
            in_j = slice(0, nelx + dj)

        return (out_i, out_j), (in_i, in_j)

    def _smooth_max(self, x):
        P = self.P
        x_pos = np.maximum(x, 0.0)
        accum = np.zeros_like(x, dtype=float)
        counts = np.zeros_like(x, dtype=float)

        for di, dj in self._offsets:
            out_s, in_s = self._slices(di, dj)
            accum[out_s] += x_pos[in_s] ** P
            counts[out_s] += 1.0

        counts = np.maximum(counts, 1.0)
        return (accum / counts + 1e-300) ** (1.0 / P)

    def _smooth_max_backward(self, x, y, sensitivity):
        P = self.P
        x_pos = np.maximum(x, 0.0)
        y_safe = np.maximum(y, 1e-300)
        grad = np.zeros_like(x, dtype=float)
        counts = np.zeros_like(x, dtype=float)

        for di, dj in self._offsets:
            out_s, _ = self._slices(di, dj)
            counts[out_s] += 1.0
        counts = np.maximum(counts, 1.0)

        for di, dj in self._offsets:
            out_s, in_s = self._slices(di, dj)
            coeff = x_pos[in_s] ** (P - 1.0) / (
                counts[out_s] * y_safe[out_s] ** (P - 1.0)
            )
            coeff = np.where(x[in_s] > 0.0, coeff, 0.0)
            grad[in_s] += sensitivity[out_s] * coeff

        return grad

    def _smooth_min(self, x):
        return 1.0 - self._smooth_max(1.0 - x)

    def _smooth_min_backward(self, x, y, sensitivity):
        return self._smooth_max_backward(1.0 - x, 1.0 - y, sensitivity)

    def forward(self, x):
        if self._identity or self._alpha <= 0.0:
            return x.copy()

        # Zero out sub-threshold densities so they don't seed dilation.
        x_thresh = np.where(x >= self._threshold, x, 0.0)

        dilated = self._smooth_max(x_thresh)
        closed = self._smooth_min(dilated)
        self._saved = dict(dilated=dilated, closed=closed, x_thresh=x_thresh)

        # Apply routing only to interior elements; boundary band passes through
        # unchanged (tool centre can sit outside the domain there).
        m = self._interior_mask
        routed = (1.0 - self._alpha * m) * x + self._alpha * m * closed
        return np.clip(routed, 0.0, 1.0)

    def backward(self, x_in, sensitivity):
        if self._identity or self._alpha <= 0.0:
            return sensitivity.copy()

        dilated = self._saved["dilated"]
        closed = self._saved["closed"]
        x_thresh = self._saved["x_thresh"]
        m = self._interior_mask

        # Gradient of the routing path (interior only).
        s_dilated = self._smooth_min_backward(dilated, closed, sensitivity * self._alpha * m)
        s_thresh = self._smooth_max_backward(x_thresh, dilated, s_dilated)

        # Direct path: boundary elements get full sensitivity, interior elements
        # get the (1-alpha) share that bypassed the closing.
        s_direct = sensitivity * (1.0 - self._alpha * m)
        return s_direct + s_thresh

    def backward_volume(self, x_in, sensitivity):
        # Keep OC's volume denominator positive; near-zero routing adjoints can
        # otherwise make -dc/dv unstable and collapse the design.
        return np.maximum(self.backward(x_in, sensitivity), 1e-6)
