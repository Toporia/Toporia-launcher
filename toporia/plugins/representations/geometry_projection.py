"""Own geometry-projection variant: fixed-radius capsules with a size variable.

The local flat-interface approximation uses the circular/spherical cap fraction
of a sample ball. Signed distance is positive INSIDE a capsule. Endpoints and
size alpha are design variables; the capsule radius is a fixed stock size.

Differences from GPTO: independent implementation (no CC-BY-NC code copied),
bounded product union instead of a p-norm, and the configured material law
penalises the combined density while volume uses the unpenalised field. Bars
float independently; shared endpoints and stacked-joint thickness are not used.

References: Norato, Bell & Tortorelli, CMAME 293 (2015) 306-327; Smith & Norato,
SMO 62 (2020) 1579-1594. The latter explains the cap approximation and capsules.
Papers: https://doi.org/10.1016/j.cma.2015.05.005 https://doi.org/10.1007/s00158-020-02552-0
"""

from itertools import product

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.representation import Representation


def cap_projection(signed_distance, window, dim):
    """Sample-ball fraction for a locally flat boundary, and its distance slope."""
    t = np.clip(np.asarray(signed_distance) / window, -1.0, 1.0)
    if dim == 2:
        root = np.sqrt(np.maximum(0.0, 1.0 - t * t))
        return 0.5 + (np.arcsin(t) + t * root) / np.pi, 2.0 * root / (np.pi * window)
    if dim == 3:
        return 0.5 + 0.75 * t - 0.25 * t ** 3, 0.75 * (1.0 - t * t) / window
    raise ValueError("cap projection supports only 2D and 3D")


class GeometryProjection(Representation):
    """Floating capsule endpoints and component activation, projected to a grid."""

    name = "geometry_projection"
    label = "Geometry projection (capsule bars)"
    use_when = (
        "Like moving components, but with round-ended capsule bars that can switch off; good for truss- "
        "like designs described by bar end points."
    )
    order = 27
    dims = (2, 3)
    advice = (
        "Use a general-vector updater such as MMA with method.move about 0.02. "
        "The fixed bar radius must cover the projection window; refine the mesh if needed. "
        "The initial fixed set of bars can vanish through its size variables, but cannot nucleate new bars."
    )
    reference = (
        'J. A. Norato, B. K. Bell, D. A. Tortorelli, "A geometry projection method for continuum-based '
        'topology optimization with discrete elements", CMAME 293 (2015) 306-327; H. Smith and '
        'J. A. Norato, "A MATLAB code for topology optimization using the geometry projection method", '
        'SMO 62 (2020) 1579-1594. Own bounded-union variant. '
        'Papers: https://doi.org/10.1016/j.cma.2015.05.005 https://doi.org/10.1007/s00158-020-02552-0'
    )
    params = (
        Param("n_x", 4, "Cells across", "Initial layout cells along x.", min=1, max=20),
        Param("n_y", 2, "Cells down", "Initial layout cells along y.", min=1, max=20),
        Param("n_z", 1, "Cells deep", "Initial layout cells along z (3D only).", min=1, max=20),
        Param("bar_radius", 2.0, "Stock bar radius", "Fixed capsule radius, shared by every bar.",
              min=0.001, max=1000.0, step=0.1, decimals=3, units="mm"),
        Param("projection_width", 0.5, "Sample window radius",
              "Radius of the projection sample ball, in the smallest element width.",
              min=0.05, max=5.0, step=0.05, decimals=2, units="elements"),
        Param("start_size", 1.0, "Initial bar size", "Initial activation alpha of every component.",
              min=0.01, max=1.0, step=0.05, decimals=2),
    )

    def __init__(self, n_x=4, n_y=2, n_z=1, bar_radius=2.0, projection_width=0.5, start_size=1.0):
        counts = (n_x, n_y, n_z)
        if any(not np.isfinite(n) or int(n) != n or n < 1 for n in counts):
            raise ValueError("layout counts must be positive integers")
        if not np.all(np.isfinite([bar_radius, projection_width, start_size])):
            raise ValueError("geometry projection controls must be finite")
        if bar_radius <= 0 or projection_width <= 0 or not 0 <= start_size <= 1:
            raise ValueError("radius/window must be positive and start_size must lie in [0, 1]")
        self.counts = tuple(int(n) for n in counts)
        self.bar_radius, self.projection_width, self.start_size = bar_radius, projection_width, start_size

    def setup(self, problem):
        self.dim = problem.dims
        if self.dim not in self.dims:
            raise ValueError("geometry projection supports only 2D and 3D")
        self.shape = problem.shape
        coordinates = [problem.elem_x, problem.elem_y]
        self.lengths = np.array([problem.Lx, problem.Ly])
        h = min(problem.dx, problem.dy)
        if self.dim == 3:
            coordinates.append(problem.elem_z)
            self.lengths = np.append(self.lengths, problem.Lz)
            h = min(h, problem.dz)
        self.points = np.stack([c.ravel() for c in coordinates], axis=-1)
        self.window = self.projection_width * h
        if self.bar_radius < self.window:
            raise ValueError("bar_radius must cover the projection window; refine the mesh or reduce projection_width")
        self.per_bar = 2 * self.dim + 1
        counts = np.array(self.counts[:self.dim])
        step = 1.0 / counts
        bars = []
        # Two diagonals per rectangle; four body diagonals per box.
        for cell in product(*(range(n) for n in counts)):
            low = np.asarray(cell) * step
            for tail in product((0, 1), repeat=self.dim - 1):
                corner = np.array((0, *tail))
                a, b = low + corner * step, low + (1 - corner) * step
                bars.append([*a, *b, self.start_size])
        self._start = np.clip(np.asarray(bars, dtype=float), 0.0, 1.0).ravel()

    def initial(self):
        return self._start.copy()

    def bounds(self):
        return np.zeros_like(self._start), np.ones_like(self._start)

    def _fields(self, z):
        bars = np.asarray(z).reshape(-1, self.per_bar)
        a = bars[:, :self.dim] * self.lengths
        b = bars[:, self.dim:2 * self.dim] * self.lengths
        vector = b - a
        offset = self.points[None] - a[:, None]
        length2 = np.sum(vector * vector, axis=1)
        dot = np.sum(offset * vector[:, None], axis=-1)
        # Collapsed segments become balls. Half/half endpoint subgradients avoid
        # NaNs there; the distance is not classically differentiable at collapse.
        t = np.divide(dot, length2[:, None], out=np.full_like(dot, 0.5),
                      where=length2[:, None] > 1e-24 * np.max(self.lengths) ** 2)
        t = np.clip(t, 0.0, 1.0)
        residual = offset - t[..., None] * vector[:, None]
        distance = np.linalg.norm(residual, axis=-1)
        normals = np.divide(residual, distance[..., None], out=np.zeros_like(residual),
                            where=distance[..., None] > 0)
        projected, slope = cap_projection(self.bar_radius - distance, self.window, self.dim)
        alpha = bars[:, -1, None]
        return alpha * projected, projected, slope, normals, t, alpha

    def density(self, z):
        local = self._fields(z)[0]
        return (1.0 - np.prod(1.0 - local, axis=0)).reshape(self.shape)

    def backward(self, z, sensitivity):
        local, projected, slope, normals, t, alpha = self._fields(z)
        outside = 1.0 - local
        before = np.concatenate([np.ones_like(outside[:1]), np.cumprod(outside, axis=0)[:-1]])
        after = np.concatenate([np.cumprod(outside[::-1], axis=0)[::-1][1:], np.ones_like(outside[:1])])
        weight = np.asarray(sensitivity).ravel()[None] * before * after
        geometry = (weight * alpha * slope)[..., None] * normals
        start = np.sum(geometry * (1.0 - t)[..., None], axis=1) * self.lengths
        end = np.sum(geometry * t[..., None], axis=1) * self.lengths
        size = np.sum(weight * projected, axis=1)
        return np.column_stack([start, end, size]).ravel()

    def outlines(self, z, points=72):
        """Nominal boundaries of active 2D bars, before domain clipping and filters."""
        if self.dim != 2:
            return None
        polygons = []
        half = max(4, int(points) // 2)
        for bar in np.asarray(z).reshape(-1, self.per_bar):
            if bar[-1] <= 0:
                continue
            a, b = bar[:2] * self.lengths, bar[2:4] * self.lengths
            theta = np.arctan2(b[1] - a[1], b[0] - a[0])
            angles = theta + np.linspace(-0.5 * np.pi, 0.5 * np.pi, half)
            front = b + self.bar_radius * np.column_stack([np.cos(angles), np.sin(angles)])
            angles = theta + np.linspace(0.5 * np.pi, 1.5 * np.pi, half)
            back = a + self.bar_radius * np.column_stack([np.cos(angles), np.sin(angles)])
            polygon = np.vstack([front, back])
            polygons.append(np.vstack([polygon, polygon[:1]]))
        return polygons
