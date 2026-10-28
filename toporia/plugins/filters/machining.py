"""Axis-direction PDE machining filter, independently written from a paper.

Høghøj & Träff, CMAME 391 (2022) 114488, doi:10.1016/j.cma.2021.114488;
readable derivation: https://arxiv.org/html/2102.12999 (sections 2 and A/B).
This is not a port of Langelaar's rotated-grid/tool-shape implementation.

Each prescribed tool side casts a downstream material shadow by solving
u.grad(T) - D laplacian(T) = rho/h_mean. Cell-centred finite volumes use
upwind advection and centred diffusion, including Robin ghost cells at the
outer box and Dirichlet ghosts at passive solids. Sparse LU factors are reused
for both the forward solve and its exact transpose. Negative-power means
intersect shadows; a clipped tanh projection bounds the physical density.

Scope: rectangular 2-D/3-D grids and Cartesian tool sides, infinitesimal tools.
Diffusion/projection are approximations, not a machinability certificate.
No cutter/holder geometry, oblique directions, or forced-void regions.
Use after a density/PDE regulariser and last in the filter chain. The initial
element-density field is calibrated to physical volume to avoid a saturated
all-solid start (the source paper likewise uses small initial design values).
"""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu
from scipy.special import logsumexp

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter


class MachiningFilter(Filter):
    """Material shadow intersection for tools approaching from selected box sides."""

    name = "machining"
    label = "PDE machining (axis directions)"
    use_when = (
        "For milled parts: every surface must be reachable by a tool from the chosen box sides. Element "
        "densities only; it does not model a finite cutter or holder."
    )
    order = 95
    dims = (2, 3)
    calibrate_initial_volume = True
    must_be_last = True
    reference = (
        'Independent Cartesian finite-volume variant of L. C. Hoghoj and E. A. Traff, '
        '"An Advection-Diffusion based Filter for Machinable Designs in Topology '
        'Optimization", CMAME 391 (2022) 114488. No finite cutter or holder geometry; '
        'diffusion/projection can leave accessibility artefacts. '
        'Papers: https://doi.org/10.1016/j.cma.2021.114488 https://arxiv.org/abs/2102.12999'
    )
    params = (
        *(Param(f"from_{word}_{axis}", axis == "y" and word == "pos", f"Tool from {sign}{axis}",
                "Tool approaches from this box side; its material shadow goes towards the "
                "opposite side. z requires 3-D. No cutter or holder geometry.")
          for axis in "xyz" for word, sign in (("pos", "+"), ("neg", "-"))),
        Param("peclet", 10000.0, "Peclet number",
              "Dimensionless advection/diffusion ratio on the longest box side. "
              "Higher values reduce diffusion; this is not an accessibility certificate.",
              min=1000.0, max=100000000.0, step=1000.0, decimals=0),
        Param("beta", 8.0, "Projection sharpness",
              "Fixed sharpness; strong projection needs small optimisation moves.",
              min=8.0, max=64.0, step=1.0, decimals=1),
        Param("eta", 0.4, "Projection threshold",
              "0.4 reduces boundary artefacts compared with the paper's 0.5. Diffusion "
              "can still create inaccessible voids near this threshold.",
              min=0.1, max=0.9, step=0.05, decimals=2),
        Param("power", -4.0, "Shadow intersection power",
              "Negative-power mean. More negative is closer to the minimum shadow.",
              min=-32.0, max=-1.0, step=1.0, decimals=1),
    )

    def __init__(self, from_pos_x=False, from_neg_x=False, from_pos_y=True, from_neg_y=False,
                 from_pos_z=False, from_neg_z=False, peclet=10000.0, beta=8.0, eta=0.4, power=-4.0):
        selected = (from_pos_x, from_neg_x, from_pos_y, from_neg_y, from_pos_z, from_neg_z)
        sides = tuple(s for s, enabled in zip(("+x", "-x", "+y", "-y", "+z", "-z"), selected,
                                              strict=True) if enabled)
        if not sides:
            raise ValueError("Tool sides: select at least one tool approach side")
        values = np.array([peclet, beta, eta, power], dtype=float)
        if (not np.all(np.isfinite(values)) or peclet < 1000 or not 8 <= beta <= 64
                or not 0.1 <= eta <= 0.9 or not -32 <= power <= -1):
            raise ValueError("Machining needs finite peclet >= 1000, beta in [8,64], "
                             "eta in [0.1,0.9], power in [-32,-1]")
        self.tool_sides = sides
        self.peclet, self.beta, self.eta, self.power = values

    def setup(self, problem, solver):
        if solver is not None and solver.representation.get("type", "element_density") != "element_density":
            raise ValueError("PDE machining currently requires element densities for its calibrated start")
        self._shape = tuple(problem.shape)
        ndim = len(self._shape)
        if ndim not in self.dims or (ndim == 2 and any(s.endswith("z") for s in self.tool_sides)):
            raise ValueError("Machining along z requires a 3-D problem")
        if np.any(getattr(problem, "void_elements", False)):
            raise ValueError("PDE machining does not support forced-void regions: overwriting "
                             "a shadow can make an inaccessible hole")
        self._solid = np.broadcast_to(getattr(problem, "passive_elements", False), self._shape).ravel()
        # Work in physical coordinates. Pe is nondimensionalised by the longest
        # side, making the same filter invariant to a change of length units.
        spacing = np.array([getattr(problem, f"d{a}", 1.0) for a in "zyx"[-ndim:]], dtype=float)
        if np.any(~np.isfinite(spacing)) or np.any(spacing <= 0):
            raise ValueError("Machining needs finite positive cell spacings")
        spacing /= np.max(spacing * self._shape)
        diffusion = 1.0 / self.peclet
        self._source = (~self._solid).astype(float) / np.mean(spacing)
        self._systems = [self._assemble(side, spacing, diffusion) for side in self.tool_sides]

    def _assemble(self, side, spacing, diffusion):
        """Assemble face fluxes divided by uniform cell volume (paper appendix A)."""
        n = int(np.prod(self._shape))
        ids = np.arange(n).reshape(self._shape)
        diagonal = np.zeros(n)
        rhs = np.zeros(n)
        rows, cols, data = [], [], []
        active = ids.ravel()[~self._solid]
        axis_u = len(self._shape) - 1 - "xyz".index(side[1])
        velocity = -1.0 if side[0] == "+" else 1.0
        coordinates = np.indices(self._shape).reshape(len(self._shape), -1)
        for axis, h in enumerate(spacing):
            d = diffusion / h**2
            stride = int(np.prod(self._shape[axis + 1:]))
            for sign in (-1, 1):
                flux = sign * velocity / h if axis == axis_u else 0.0
                interior = (coordinates[axis, active] + sign >= 0) & (
                    coordinates[axis, active] + sign < self._shape[axis])
                p = active[interior]
                neighbor = p + sign * stride
                free = ~self._solid[neighbor]
                p_free, neighbor_free = p[free], neighbor[free]
                diagonal[p_free] += d + max(flux, 0.0)
                rows.append(p_free)
                cols.append(neighbor_free)
                data.append(np.full(len(p_free), -d + min(flux, 0.0)))
                # At a passive solid face, the ghost is 2 - T_P (T_face=1).
                p_solid = p[~free]
                diagonal[p_solid] += 2 * d + abs(flux)
                rhs[p_solid] += 2 * d - 2 * min(flux, 0.0)
                # Robin: T_face + D/s * dT/dn = 0, T_face=(T_P+T_G)/2.
                # Upwinding uses the ghost on inflow, the cell on outflow.
                boundary = active[~interior]
                ratio = 2 * diffusion * np.mean(spacing) / h
                ghost = (ratio - 1) / (ratio + 1)
                diagonal[boundary] += d * (1 - ghost) + max(flux, 0.0) + min(flux, 0.0) * ghost
        diagonal[self._solid] = 1.0
        rhs[self._solid] = 1.0
        rows.append(np.arange(n))
        cols.append(np.arange(n))
        data.append(diagonal)
        matrix = coo_matrix((np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))),
                            shape=(n, n)).tocsc()
        return splu(matrix), rhs

    def _fields(self, x):
        source = self._source * np.asarray(x, dtype=float).ravel()
        shadows = np.stack([lu.solve(source + rhs) for lu, rhs in self._systems])
        # A tiny offset makes the negative mean differentiable even at all-void.
        # Log space avoids over/underflow for large shadows or negative powers.
        positive = np.maximum(shadows, 0.0) + 1e-12
        logs = self.power * np.log(positive)
        total = logsumexp(logs, axis=0)
        mean = np.exp((total - np.log(len(shadows))) / self.power)
        weights = np.exp(logs - total) * mean / positive
        aggregate = np.maximum(mean - 1e-12, 0.0)
        return aggregate, weights

    def _projection(self, aggregate):
        # The paper's normalised tanh exceeds one slightly when its input does.
        # Clamp that saturated branch explicitly and include it in the adjoint.
        t = np.tanh(self.beta * (np.minimum(aggregate, 1.0) - self.eta))
        a = np.tanh(self.beta * self.eta)
        denominator = a + np.tanh(self.beta * (1 - self.eta))
        density = (a + t) / denominator
        derivative = self.beta * (1 - t * t) / denominator * (aggregate < 1)
        density[self._solid] = 1.0
        derivative[self._solid] = 0.0
        return density, derivative

    def forward(self, x):
        aggregate, _ = self._fields(x)
        return self._projection(aggregate)[0].reshape(self._shape)

    def backward(self, x_in, sensitivity):
        aggregate, weights = self._fields(x_in)
        seed = self._projection(aggregate)[1] * np.asarray(sensitivity).ravel()
        gradient = np.zeros(seed.shape)
        for (lu, _), weight in zip(self._systems, weights, strict=True):
            gradient += self._source * lu.solve(seed * weight, trans="T")
        return gradient.reshape(self._shape)
