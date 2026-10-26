"""Cell-centred Gaynor–Guest support projection, with a full reverse sweep.

Independent discretisation of Gaynor & Guest, SMO 54 (2016) 1157–1172,
doi:10.1007/s00158-016-1551-x, sections 2.1–2.5. Also derived in Gaynor's
2015 JHU dissertation, chapter 3 (equations 3.2–3.6). No published code copied.

psi -> phi = psi * H_T(mean(phi in lower support wedge))
    -> mu = local_cone_average(phi) -> rho = 1-exp(-beta*mu)+mu*exp(-beta).

The support recursion runs from the build plate upwards. Its adjoint runs
backwards through every lower-layer dependency; differentiating only the
local product misses the principal coupling. The first cell layer is supported
by the build plate. Both neighbourhoods are truncated at the box boundary.

Unlike the paper's nodal examples, the design points here are cell centres
(locations allowed in its section 2.1). Only 2-D Cartesian builds are supported.
The support threshold is grid/angle dependent; smoothing and finite projection
do not certify an exact boundary angle or minimum feature size. Forced solid
and void regions are refused rather than overwritten after manufacturing.
"""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter


class SelfSupportProjection(Filter):
    """Lower-wedge support gate followed by local exponential projection."""

    name = "self_support"
    label = "Gaynor–Guest self-support projection (2-D)"
    order = 96
    must_be_last = True
    calibrate_initial_volume = True
    schedulable = ("beta_local", "beta_support")
    reference = (
        'Independent cell-centred variant of A. T. Gaynor and J. K. Guest, '
        '"Topology optimization considering overhang constraints: Eliminating sacrificial '
        'support material in additive manufacturing through design", SMO 54 (2016) '
        '1157-1172. Exact reverse sweep of the support recursion. 2-D axis builds; '
        'the threshold depends on the discrete wedge. Requires element densities, no forced '
        'regions, and the final filter position. No exact angle/size certificate. '
        'Papers: https://doi.org/10.1007/s00158-016-1551-x'
    )
    params = (
        Param("direction", "+y", "Build direction",
              "Build away from the opposite box face; +y builds upwards from the bottom.",
              choices=(("+y", "Up (+y)"), ("-y", "Down (-y)"),
                       ("+x", "Right (+x)"), ("-x", "Left (-x)"))),
        Param("rmin", 2.4, "Local projection radius",
              "Radius in shortest-cell widths. The support wedge radius is 1.5 times this. "
              "This is a nominal projection radius, not a minimum-size certificate.",
              min=1.0, max=20.0, step=0.1, decimals=2, units="el"),
        Param("angle", 45.0, "Minimum support angle",
              "Angle from the build plate: 90 allows vertical supports only. Discrete "
              "wedges change in steps; calibrate the threshold for the chosen grid and angle.",
              min=15.0, max=90.0, step=5.0, decimals=1, units="°"),
        Param("threshold", 0.1, "Support threshold",
              "Threshold on the mean lower-wedge field. Smaller values permit weaker "
              "support. It must be checked against the discrete support geometry.",
              min=0.01, max=0.9, step=0.01, decimals=3),
        Param("beta_support", 20.0, "Support sharpness",
              "Fixed tanh sharpness for the support gate; large values can stall growth.",
              min=1.0, max=80.0, step=1.0, decimals=1),
        Param("beta_local", 35.0, "Local sharpness",
              "Fixed exponential local projection. Use small MMA moves and preferably RAMP.",
              min=1.0, max=80.0, step=1.0, decimals=1),
    )

    def __init__(self, direction="+y", rmin=2.4, angle=45.0, threshold=0.1,
                 beta_support=20.0, beta_local=35.0):
        if direction not in ("+y", "-y", "+x", "-x"):
            raise ValueError("Self-support build direction must be +x, -x, +y or -y")
        values = np.array([rmin, angle, threshold, beta_support, beta_local], dtype=float)
        if (not np.all(np.isfinite(values)) or not 1 <= rmin <= 20 or not 15 <= angle <= 90
                or not 0.01 <= threshold <= 0.9 or not 1 <= beta_support <= 80
                or not 1 <= beta_local <= 80):
            raise ValueError("Self-support needs finite rmin in [1,20], angle in [15,90], "
                             "threshold in [0.01,0.9], and sharpnesses in [1,80]")
        self.direction = direction
        self.rmin, self.angle, self.threshold, self.beta_support, self.beta_local = values
        self._axis = 0 if direction[1] == "y" else 1

    def _layers(self, x):
        view = np.moveaxis(x, self._axis, 0)
        return view if self.direction[0] == "+" else view[::-1]

    def _restore(self, layers):
        if self.direction[0] == "-":
            layers = layers[::-1]
        return np.ascontiguousarray(np.moveaxis(layers, 0, self._axis))

    def setup(self, problem, solver):
        if len(problem.shape) != 2:
            raise ValueError("Gaynor–Guest self-support currently requires a 2-D problem")
        if np.any(getattr(problem, "passive_elements", False)) or np.any(getattr(problem, "void_elements", False)):
            raise ValueError("Self-support projection does not support forced solid/void regions: "
                             "physical overwrites can invalidate the support geometry")
        if solver is not None and solver.representation.get("type", "element_density") != "element_density":
            raise ValueError("Self-support projection currently requires element densities for its calibrated start")
        spacing = np.array([getattr(problem, "dy", 1.0), getattr(problem, "dx", 1.0)])
        if np.any(~np.isfinite(spacing)) or np.any(spacing <= 0):
            raise ValueError("Self-support needs finite positive cell spacings")
        radius = self.rmin * np.min(spacing)
        self._shape = tuple(problem.shape)
        layer_shape = self._layers(np.empty(self._shape)).shape
        h, w = spacing[self._axis], spacing[1 - self._axis]
        support_radius = 1.5 * radius
        offsets = [(depth, shift) for depth in range(1, int(np.floor(support_radius / h)) + 1)
                   for shift in range(-int(np.floor(support_radius / w)), int(np.floor(support_radius / w)) + 1)
                   if np.hypot(depth * h, shift * w) <= support_radius + 1e-12 * radius
                   and abs(shift * w) <= depth * h / np.tan(np.deg2rad(self.angle)) + 1e-12 * radius]
        if not offsets:
            raise ValueError("Support wedge contains no previous layer; increase the projection radius")
        # One rectangular, row-normalised operator per predecessor depth. The
        # row sweep uses only already computed phi; the transpose reverses it.
        width = layer_shape[1]
        self._support = []
        for layer in range(layer_shape[0]):
            start = max(0, layer - max(depth for depth, _ in offsets))
            row, col = [], []
            for depth, shift in offsets:
                if layer < depth:
                    continue
                target = np.arange(max(0, -shift), min(width, width - shift))
                row.extend(target)
                col.extend((layer - depth - start) * width + target + shift)
            matrix = coo_matrix((np.ones(len(row)), (row, col)),
                                shape=(width, (layer - start) * width)).tocsr()
            counts = np.asarray(matrix.sum(axis=1)).ravel()
            self._support.append((start, matrix.multiply((1 / np.maximum(counts, 1))[:, None]).tocsr()))
        # The local projection uses physical distances and a truncated cone.
        points = np.stack(np.indices(self._shape), axis=-1).reshape(-1, 2) * spacing
        tree = cKDTree(points)
        rows, cols, data = [], [], []
        for i, neighbors in enumerate(tree.query_ball_point(points, radius)):
            weights = np.maximum(radius - np.linalg.norm(points[neighbors] - points[i], axis=1), 0)
            rows.extend([i] * len(neighbors))
            cols.extend(neighbors)
            data.extend(weights / weights.sum())
        self._local = coo_matrix((data, (rows, cols)), shape=(len(points), len(points))).tocsr()

    def _gate(self, mean):
        a = np.tanh(self.beta_support * self.threshold)
        t = np.tanh(self.beta_support * (mean - self.threshold))
        denominator = a + np.tanh(self.beta_support * (1 - self.threshold))
        return (a + t) / denominator, self.beta_support * (1 - t * t) / denominator

    def _supported(self, x):
        psi = self._layers(np.asarray(x, dtype=float))
        phi = np.zeros(psi.shape)
        support, derivative = np.ones(psi.shape), np.zeros(psi.shape)
        phi[0] = psi[0]  # the first layer touches the build plate
        for layer in range(1, len(phi)):
            start, matrix = self._support[layer]
            support[layer], derivative[layer] = self._gate(matrix @ phi[start:layer].ravel())
            phi[layer] = psi[layer] * support[layer]
        return phi, support, derivative

    def forward(self, x):
        phi, _, _ = self._supported(x)
        mean = self._local @ self._restore(phi).ravel()
        return (-np.expm1(-self.beta_local * mean) + mean * np.exp(-self.beta_local)).reshape(self._shape)

    def backward(self, x_in, sensitivity):
        phi, support, derivative = self._supported(x_in)
        mean = self._local @ self._restore(phi).ravel()
        slope = self.beta_local * np.exp(-self.beta_local * mean) + np.exp(-self.beta_local)
        g_phi = self._layers((self._local.T @ (np.asarray(sensitivity).ravel() * slope)).reshape(self._shape)).copy()
        psi = self._layers(x_in)
        gradient = np.empty(phi.shape)
        for layer in range(len(phi) - 1, 0, -1):
            gradient[layer] = g_phi[layer] * support[layer]
            start, matrix = self._support[layer]
            g_phi[start:layer] += (matrix.T @ (g_phi[layer] * psi[layer] * derivative[layer])).reshape(layer - start, -1)
        gradient[0] = g_phi[0]
        return self._restore(gradient)
