# plugins/physics/truss.py — pin-jointed bars on a ground structure, 2-D and 3-D (To do item 3).
#
# A ground structure is a grid of nodes in the design domain with a bar between every pair
# of nodes within reach; the optimiser sizes the bars, and the ones that end up thin are the
# ones the structure does not need.  The classic reference is Dorn, Gomory & Greenberg
# (1964); the formulation here is the minimum-compliance one with a volume budget:
#
#     min C = Σ_k w_k f_kᵀ u_k   over the bar areas a,   K(a) u_k = f_k,   Σ a_i L_i ≤ V
#
#   nodes      every s-th mesh node along each axis (s from the node spacing), plus
#              point supports and point loads, so they land on a node
#   bars       node pairs whose index offsets are at most `reach` along every axis and
#              have no common divisor (so no bar overlaps a shorter collinear one); bars
#              through void elements are left out
#   stiffness  k_i = E a_i / L_i · [c cᵀ  −c cᵀ; −c cᵀ  c cᵀ], c the bar's unit vector
#   gradient   dC/da_i = −Σ_k w_k (E / L_i) (c · Δu_ik)²,  so C is convex in a (Svanberg)
#   vibration  K φ = λ M φ with the bar mass lumped at the nodes (and joints, truss_nodes.py);
#              with φᵀMφ = 1:  dλ/da_i = φ_iᵀ (k_i / a_i) φ_i − λ φ_iᵀ (∂M/∂a_i) φ_i
#
# A truss becomes a density field by drawing every bar as a capsule: in 2-D a band as wide
# as its area (unit thickness), in 3-D a cylinder of the same cross-section, smoothed over
# one element (bars_to_density).  That density can then be checked and optimised by any
# continuum method on the same scenario.
#
# Reference: W. S. Dorn, R. E. Gomory, H. J. Greenberg, "Automatic design of optimal
# structures", J. Mécanique 3 (1964) 25-52; W. Achtziger, "Truss topology optimization
# including bar properties different for tension and compression", SMO 12 (1996) 63-74.

from dataclasses import dataclass
from math import gcd

import numpy as np


@dataclass
class GroundStructure:
    """Nodes, bars and the loads and supports on them."""
    nodes: np.ndarray        # (n, dims) coordinates in mm
    bars: np.ndarray         # (b, 2) node indices
    lengths: np.ndarray      # (b,) in mm
    directions: np.ndarray   # (b, dims) unit vectors
    fixed: np.ndarray        # fixed DOF indices
    forces: list             # one (n * dims,) vector per load case
    weights: np.ndarray      # load-case weights
    dims: int

    @property
    def ndof(self):
        """Degrees of freedom: dims per node."""
        return self.nodes.shape[0] * self.dims


def node_coordinates_grid(problem):
    """Coordinates of every mesh node, shaped like the node masks plus one axis."""
    return _node_coordinates(problem)


def _node_coordinates(problem):
    if problem.dims == 3:
        return np.stack([problem.node_x, problem.node_y, problem.node_z], axis=-1)
    return np.stack([problem.node_x, problem.node_y], axis=-1)


def _point_like(mask, limit=4):
    """True for a support or load region of a few nodes: it must be a truss node itself."""
    return 0 < int(np.count_nonzero(mask)) <= limit


def _void_samples(problem, a, b, samples=7):
    """True when a bar between points a and b passes through a void element."""
    if not np.any(problem.void_elements):
        return False
    t = np.linspace(0.05, 0.95, samples)[:, None]
    points = a + t * (b - a)
    steps = [problem.dx, problem.dy] + ([problem.dz] if problem.dims == 3 else [])
    counts = [problem.nelx, problem.nely] + ([problem.nelz] if problem.dims == 3 else [])
    index = [np.clip((points[:, k] // steps[k]).astype(int), 0, counts[k] - 1) for k in range(problem.dims)]
    cells = (index[2], index[1], index[0]) if problem.dims == 3 else (index[1], index[0])
    return bool(np.any(problem.void_elements[cells]))


def ground_structure(problem, spacing, reach=2):
    """The ground structure of a problem: nodes every `spacing` mm, bars to neighbours within `reach`."""
    coordinates = _node_coordinates(problem)
    shape = coordinates.shape[:-1]
    dims = problem.dims
    steps = [problem.dx, problem.dy] + ([problem.dz] if dims == 3 else [])
    counts = [problem.nelx, problem.nely] + ([problem.nelz] if dims == 3 else [])
    stride = [_divisor_near(count, spacing / step) for count, step in zip(counts, steps, strict=True)]
    # Index grids in array order: (y, x) or (z, y, x).
    grids = np.meshgrid(*[np.arange(n) for n in shape], indexing="ij")
    axis_of = {0: dims - 1, 1: dims - 2, 2: 0} if dims == 3 else {0: 1, 1: 0}   # x/y/z -> array axis
    on_grid = np.ones(shape, bool)
    for k in range(dims):
        on_grid &= grids[axis_of[k]] % stride[k] == 0
    masks = [problem.fixed_nodes, problem.fixed_x_nodes, problem.fixed_y_nodes]
    if dims == 3:
        masks.append(problem.fixed_z_nodes)
    point_masks = [m for m in masks + list(problem.load_node_sets) if _point_like(m)]
    chosen = on_grid.copy()
    for mask in point_masks:
        chosen |= mask
    # A node all of whose elements are void is not part of the domain.
    solid = ~problem.void_elements
    padded = np.zeros(tuple(n + 1 for n in shape), bool)
    for offset in np.ndindex(*(2,) * dims):
        padded[tuple(slice(o, o + n - 1) for o, n in zip(offset, shape, strict=True))] |= solid
    chosen &= padded[tuple(slice(0, n) for n in shape)]

    index = -np.ones(shape, int)
    picked = np.argwhere(chosen)
    index[tuple(picked.T)] = np.arange(len(picked))
    nodes = coordinates[tuple(picked.T)]

    # Bars: offsets in grid units (multiples of the stride), primitive, half of them.
    unit = np.array([stride[axis_k] for axis_k in _array_axis_order(dims)])
    offsets = []
    for offset in np.ndindex(*(2 * reach + 1,) * dims):
        d = np.array(offset) - reach
        if not d.any() or gcd(*[int(abs(v)) for v in d]) != 1:
            continue
        first = d[np.flatnonzero(d)[0]]
        if first > 0:
            offsets.append(d * unit)
    pairs = []
    for d in offsets:
        target = picked + d
        valid = np.all((target >= 0) & (target < np.array(shape)), axis=1)
        src, dst = picked[valid], target[valid]
        ok = index[tuple(dst.T)] >= 0
        pairs.append(np.stack([index[tuple(src[ok].T)], index[tuple(dst[ok].T)]], axis=1))
    # Point nodes off the grid connect to every grid node within reach of them.
    for node in np.argwhere(chosen & ~on_grid):
        near = picked[np.all(np.abs(picked - node) <= reach * unit, axis=1)]
        near = near[np.any(near != node, axis=1)]
        here = index[tuple(node)]
        pairs.append(np.stack([np.full(len(near), here), index[tuple(near.T)]], axis=1))
    bars = np.unique(np.sort(np.concatenate(pairs), axis=1), axis=0) if pairs else np.zeros((0, 2), int)
    bars = bars[bars[:, 0] != bars[:, 1]]
    keep = np.array([not _void_samples(problem, nodes[i], nodes[j]) for i, j in bars], bool)
    bars = bars[keep] if len(bars) else bars
    vectors = nodes[bars[:, 1]] - nodes[bars[:, 0]]
    lengths = np.linalg.norm(vectors, axis=1)

    fixed = []
    def dofs(mask, components):
        ids = index[mask & chosen]
        ids = ids[ids >= 0]
        for c in components:
            fixed.extend(ids * dims + c)
    dofs(problem.fixed_nodes, range(dims))
    dofs(problem.fixed_x_nodes, [0])
    dofs(problem.fixed_y_nodes, [1])
    if dims == 3:
        dofs(problem.fixed_z_nodes, [2])

    forces, weights = [], []
    scenario = problem.scenario
    for case in scenario.load_cases:
        force = np.zeros(len(nodes) * dims)
        angle = np.deg2rad(case.Fa)
        vector = case.Fmag * np.array([np.cos(angle), np.sin(angle)] + ([0.0] if dims == 3 else []))
        for mask in problem.load_node_sets:
            where = np.argwhere(mask)
            if not len(where):
                continue
            per_node = vector / len(where)
            for node in where:
                target = _nearest(nodes, coordinates[tuple(node)])
                force[target * dims: target * dims + dims] += per_node
        forces.append(force)
        weights.append(case.weight)
    return GroundStructure(nodes, bars, lengths, vectors / lengths[:, None], np.unique(np.array(fixed, int)),
                           forces, np.array(weights, float), dims)


def _divisor_near(count, target):
    """The divisor of `count` elements closest to `target`, so nodes fall on both ends of the axis."""
    divisors = [d for d in range(1, count + 1) if count % d == 0]
    return min(divisors, key=lambda d: (abs(np.log(d / max(target, 1e-9))), d))


def _array_axis_order(dims):
    """Stride index for each array axis: (y, x) or (z, y, x) -> x=0, y=1, z=2."""
    return (2, 1, 0) if dims == 3 else (1, 0)


def _nearest(nodes, point):
    return int(np.argmin(np.sum((nodes - point) ** 2, axis=1)))


class TrussSolver:
    """Assembles and solves K(a) u = f on a ground structure, and its lowest natural mode."""

    def __init__(self, structure, E, springs=None):
        from scipy import sparse
        self.s, self.E = structure, float(E)
        dims = structure.dims
        b = len(structure.bars)
        dof = np.concatenate([structure.bars[:, :1] * dims + np.arange(dims),
                              structure.bars[:, 1:] * dims + np.arange(dims)], axis=1)       # (b, 2 dims)
        self.dof = dof
        cc = np.einsum("bi,bj->bij", structure.directions, structure.directions)
        block = np.block([[cc, -cc], [-cc, cc]]) if b else np.zeros((0, 2 * dims, 2 * dims))
        self.unit = block * (self.E / structure.lengths)[:, None, None]                      # k_i / a_i
        self.rows = np.repeat(dof, 2 * dims, axis=1).ravel()
        self.cols = np.tile(dof, (1, 2 * dims)).ravel()
        free = np.ones(structure.ndof, bool)
        free[structure.fixed] = False
        self.free = np.flatnonzero(free)
        self._sparse = sparse
        # Anchor springs (truss_nodes.py): density-independent stiffness on the diagonal.
        self.springs = np.zeros(structure.ndof) if springs is None else np.asarray(springs, dtype=float)

    def stiffness(self, areas):
        """K(a) on the free DOFs, springs included."""
        s = self.s
        values = (self.unit * areas[:, None, None]).ravel()
        K = self._sparse.coo_matrix((values, (self.rows, self.cols)), shape=(s.ndof, s.ndof)).tocsc()
        if self.springs.any():
            K = K + self._sparse.diags(self.springs, format="csc")
        return K[self.free][:, self.free]

    def solve(self, areas):
        """Displacements per load case, compliance, and dC/da."""
        from scipy.sparse.linalg import spsolve
        s = self.s
        K = self.stiffness(areas)
        compliance, gradient, displacements = 0.0, np.zeros_like(areas), []
        for force, weight in zip(s.forces, s.weights, strict=True):
            u = np.zeros(s.ndof)
            u[self.free] = spsolve(K, force[self.free])
            ue = u[self.dof]                                                    # (b, 2 dims)
            energy = np.einsum("bi,bij,bj->b", ue, self.unit, ue)               # u_iᵀ k_i u_i / a_i
            compliance += weight * float(force @ u)
            gradient -= weight * energy
            displacements.append(u)
        return displacements, compliance, gradient

    def lowest_mode(self, areas, node_mass, mass_slope):
        """The lowest eigenvalue λ = ω² of K φ = λ M φ, its mode (full length, φᵀMφ = 1) and dλ/da.

        `node_mass` is the lumped mass per node; `mass_slope[i]` is d(mass at each end)/d(a_i).
        """
        from scipy.sparse.linalg import eigsh
        s, dims = self.s, self.s.dims
        K = self.stiffness(areas)
        mass = np.repeat(node_mass, dims)[self.free]
        M = self._sparse.diags(mass, format="csc")
        count = min(3, K.shape[0] - 1)
        values, vectors = eigsh(K, k=count, M=M, sigma=0.0, which="LM")
        order = np.argsort(values)
        lam, phi_free = float(values[order[0]]), vectors[:, order[0]]
        phi_free = phi_free / np.sqrt(float(phi_free @ (mass * phi_free)))
        phi = np.zeros(s.ndof)
        phi[self.free] = phi_free
        pe = phi[self.dof]                                                  # (b, 2 dims)
        stiff = np.einsum("bi,bij,bj->b", pe, self.unit, pe)
        ends = phi.reshape(-1, dims)
        kinetic = np.sum(ends[s.bars[:, 0]] ** 2, axis=1) + np.sum(ends[s.bars[:, 1]] ** 2, axis=1)
        return lam, phi, stiff - lam * mass_slope * kinetic

    def axial_forces(self, areas, u):
        """Bar forces N_i = E a_i / L_i · c · Δu (tension positive) for one load case."""
        s, dims = self.s, self.s.dims
        du = u[s.bars[:, 1, None] * dims + np.arange(dims)] - u[s.bars[:, 0, None] * dims + np.arange(dims)]
        return self.E * areas / s.lengths * np.einsum("bi,bi->b", s.directions, du)


def bar_radius(areas, dims):
    """Half the width of a bar of area a: a/2 in 2-D (unit thickness), √(a/π) in 3-D."""
    return areas / 2.0 if dims == 2 else np.sqrt(areas / np.pi)


def bars_to_density(problem, structure, areas, threshold=1e-3):
    """Draw every bar as a capsule on the element grid; returns a density shaped like the problem."""
    dims = structure.dims
    centres = (np.stack([problem.elem_x, problem.elem_y, problem.elem_z], axis=-1) if dims == 3
               else np.stack([problem.elem_x, problem.elem_y], axis=-1))
    flat = centres.reshape(-1, dims)
    density = np.zeros(len(flat))
    h = min(problem.dx, problem.dy, *( [problem.dz] if dims == 3 else []))
    radii = bar_radius(areas, dims)
    big = areas > threshold * max(float(np.max(areas)), 1e-30)
    for (i, j), r in zip(structure.bars[big], radii[big], strict=True):
        a, b = structure.nodes[i], structure.nodes[j]
        low, high = np.minimum(a, b) - r - h, np.maximum(a, b) + r + h
        near = np.all((flat >= low) & (flat <= high), axis=1)
        if not near.any():
            continue
        p = flat[near]
        ab = b - a
        t = np.clip(((p - a) @ ab) / float(ab @ ab), 0.0, 1.0)
        distance = np.linalg.norm(p - (a + t[:, None] * ab), axis=1)
        # A capsule smoothed over one element: full inside, empty one element outside.
        cover = np.clip((r - distance) / h + 0.5, 0.0, 1.0)
        density[near] = np.maximum(density[near], cover)
    density = density.reshape(problem.shape)
    return np.clip(density, problem.lower_bound, problem.upper_bound)
