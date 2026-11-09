# toporia_library/physics/t3_mesh.py — an unstructured triangle mesh and linear triangle elements (Wave 5).
#
# The structured grid follows the axes: a round hole becomes a staircase of squares.  An
# unstructured mesh follows the geometry.  This one is built in three steps:
#
#   points     a lattice of near-equilateral triangles of side h inside the domain, the
#              domain's edges sampled every h, and every circular hole's rim sampled every h
#              (lattice points closer than h/2 to a rim or edge are dropped, so no sliver forms)
#   triangles  the Delaunay triangulation of the points (scipy.spatial.Delaunay)
#   cleaning   triangles whose centroid lies in a hole or in removed material (the problem's
#              void elements) are dropped; those in forced-solid material are kept and fixed
#
# Each triangle is a constant-strain (T3) plane-stress element:
#
#     B = (1/2A) [[b1 0 b2 0 b3 0], [0 c1 0 c2 0 c3], [c1 b1 c2 b2 c3 b3]],
#     b_i = y_j − y_k,  c_i = x_k − x_j  (i, j, k cyclic),     K_e = A t Bᵀ D B,
#
# with D the isotropic plane-stress matrix (E = 1; the material law scales it).  Supports
# and loads come from the meshed problem's node masks: every mesh node nearest to a
# supported grid node is supported the same way, and every load region's total force is
# shared by the mesh nodes nearest to its grid nodes, so a load does not depend on the mesh.
#
# Reference: O. C. Zienkiewicz, R. L. Taylor, The Finite Element Method, vol. 1 (the CST);
# unstructured-mesh topology optimisation as in C. Talischi et al., SMO 45 (2012) 309-328.

from dataclasses import dataclass

import numpy as np


@dataclass
class TriangleMesh:
    """Nodes, triangles and what lies on them."""
    nodes: np.ndarray        # (n, 2) in mm
    triangles: np.ndarray    # (e, 3) node indices, counter-clockwise
    areas: np.ndarray        # (e,)
    centroids: np.ndarray    # (e, 2)
    passive: np.ndarray      # (e,) bool: forced solid
    fixed: np.ndarray        # fixed DOF indices
    forces: list             # one (2n,) vector per load case
    weights: np.ndarray


def _holes(scenario):
    """Circular holes (cx, cy, r) of a scenario: preset holes and void circle objects."""
    found = [(hole.cx, hole.cy, hole.r_void) for hole in scenario.holes if hole.r_void > 0]
    for obj in scenario.regions or ():
        if obj.get("role") == "void" and obj.get("shape") == "circle" and not any(obj.get("rotation", [0, 0, 0])):
            w, h, _ = obj["size"]
            if abs(w - h) < 1e-9:
                found.append((obj["position"][0], obj["position"][1], w / 2))
    return found


def build_mesh(problem, size):
    """The triangle mesh of a 2-D problem, with elements of about `size` mm."""
    from scipy.spatial import Delaunay
    if problem.dims != 2:
        raise ValueError("The unstructured triangle mesh is 2-D")
    Lx, Ly, h = problem.Lx, problem.Ly, float(size)
    holes = _holes(problem.scenario)
    # Lattice of near-equilateral triangles.
    rows = int(np.ceil(Ly / (h * np.sqrt(3) / 2))) + 1
    lattice = []
    for row in range(rows):
        y = min(row * h * np.sqrt(3) / 2, Ly)
        offset = 0.5 * h if row % 2 else 0.0
        lattice += [(x, y) for x in np.arange(offset, Lx + 1e-9, h)]
    lattice = np.array(lattice)
    # The edges, sampled every h.
    nx, ny = max(int(round(Lx / h)), 1), max(int(round(Ly / h)), 1)
    edge = np.vstack([np.column_stack([np.linspace(0, Lx, nx + 1), np.zeros(nx + 1)]),
                      np.column_stack([np.linspace(0, Lx, nx + 1), np.full(nx + 1, Ly)]),
                      np.column_stack([np.zeros(ny + 1), np.linspace(0, Ly, ny + 1)]),
                      np.column_stack([np.full(ny + 1, Lx), np.linspace(0, Ly, ny + 1)])])
    keep = np.ones(len(lattice), bool)
    keep &= (lattice[:, 0] > 0.5 * h) & (lattice[:, 0] < Lx - 0.5 * h)
    keep &= (lattice[:, 1] > 0.5 * h) & (lattice[:, 1] < Ly - 0.5 * h)
    rims = []
    for cx, cy, r in holes:
        count = max(int(np.ceil(2 * np.pi * r / h)), 8)
        angle = np.linspace(0, 2 * np.pi, count, endpoint=False)
        rim = np.column_stack([cx + r * np.cos(angle), cy + r * np.sin(angle)])
        rims.append(rim[(rim[:, 0] >= 0) & (rim[:, 0] <= Lx) & (rim[:, 1] >= 0) & (rim[:, 1] <= Ly)])
        keep &= np.hypot(lattice[:, 0] - cx, lattice[:, 1] - cy) > r + 0.5 * h
    points = np.vstack([lattice[keep], edge, *rims]) if rims else np.vstack([lattice[keep], edge])
    points = np.unique(np.round(points, 9), axis=0)
    triangulation = Delaunay(points)
    triangles = triangulation.simplices
    corners = points[triangles]
    centroids = corners.mean(axis=1)
    areas = 0.5 * ((corners[:, 1, 0] - corners[:, 0, 0]) * (corners[:, 2, 1] - corners[:, 0, 1])
                   - (corners[:, 2, 0] - corners[:, 0, 0]) * (corners[:, 1, 1] - corners[:, 0, 1]))
    flip = areas < 0                                            # counter-clockwise everywhere
    triangles[flip] = triangles[flip][:, [0, 2, 1]]
    areas = np.abs(areas)
    inside = areas > 1e-12 * h * h
    for cx, cy, r in holes:
        inside &= np.hypot(centroids[:, 0] - cx, centroids[:, 1] - cy) > r
    cell = _cell_of(problem, centroids)
    inside &= ~problem.void_elements[cell]
    triangles, areas, centroids = triangles[inside], areas[inside], centroids[inside]
    cell = (cell[0][inside], cell[1][inside])
    used = np.unique(triangles)
    renumber = -np.ones(len(points), int)
    renumber[used] = np.arange(len(used))
    nodes, triangles = points[used], renumber[triangles]
    passive = problem.passive_elements[cell]
    fixed, forces, weights = _boundary_conditions(problem, nodes)
    return TriangleMesh(nodes, triangles, areas, centroids, passive, fixed, forces, weights)


def _cell_of(problem, points):
    """The structured element (row, column) under each point."""
    column = np.clip((points[:, 0] / problem.dx).astype(int), 0, problem.nelx - 1)
    row = np.clip((points[:, 1] / problem.dy).astype(int), 0, problem.nely - 1)
    return row, column


def _nearest(nodes, point):
    return int(np.argmin(np.sum((nodes - point) ** 2, axis=1)))


def _boundary_conditions(problem, nodes):
    """Supports and per-load-case forces on the triangle mesh, from the problem's node masks."""
    grid = np.stack([problem.node_x, problem.node_y], axis=-1)
    fixed = []
    for mask, components in ((problem.fixed_nodes, (0, 1)), (problem.fixed_x_nodes, (0,)),
                             (problem.fixed_y_nodes, (1,))):
        for point in grid[mask]:
            node = _nearest(nodes, point)
            fixed += [2 * node + c for c in components]
    forces, weights = [], []
    for index, case in enumerate(problem.scenario.load_cases):
        force = np.zeros(2 * len(nodes))
        regional = getattr(problem, "region_loads", None)
        if regional:
            entries = [(mask, vector) for case_index, mask, vector in regional if case_index == index]
        else:
            angle = np.deg2rad(case.Fa)
            vector = case.Fmag * np.array([np.cos(angle), np.sin(angle)])
            entries = [(mask, vector) for mask in problem.load_node_sets]
        for mask, vector in entries:
            points = grid[mask]
            for point in points:
                node = _nearest(nodes, point)
                force[2 * node: 2 * node + 2] += np.asarray(vector, float)[:2] / max(len(points), 1)
        forces.append(force)
        weights.append(case.weight)
    return np.unique(np.array(fixed, int)), forces, np.array(weights, float)


def element_matrices(mesh, nu, thickness=1.0):
    """K_e = A t Bᵀ D B of every triangle at unit Young's modulus, (e, 6, 6)."""
    D = np.array([[1.0, nu, 0.0], [nu, 1.0, 0.0], [0.0, 0.0, (1.0 - nu) / 2.0]]) / (1.0 - nu ** 2)
    p = mesh.nodes[mesh.triangles]                                   # (e, 3, 2)
    b = np.stack([p[:, 1, 1] - p[:, 2, 1], p[:, 2, 1] - p[:, 0, 1], p[:, 0, 1] - p[:, 1, 1]], axis=1)
    c = np.stack([p[:, 2, 0] - p[:, 1, 0], p[:, 0, 0] - p[:, 2, 0], p[:, 1, 0] - p[:, 0, 0]], axis=1)
    B = np.zeros((len(p), 3, 6))
    B[:, 0, 0::2], B[:, 1, 1::2], B[:, 2, 0::2], B[:, 2, 1::2] = b, c, c, b
    B /= (2.0 * mesh.areas)[:, None, None]
    return np.einsum("eki,kl,elj->eij", B, D, B) * (mesh.areas * thickness)[:, None, None]


def triangle_dofs(mesh):
    """(e, 6) DOF indices: x and y of each corner."""
    t = mesh.triangles
    return np.stack([2 * t[:, 0], 2 * t[:, 0] + 1, 2 * t[:, 1], 2 * t[:, 1] + 1, 2 * t[:, 2], 2 * t[:, 2] + 1], axis=1)


def on_grid(problem, mesh, values):
    """Triangle values sampled at the structured grid's element centres (for the engine's record)."""
    centres = np.column_stack([problem.elem_x.ravel(), problem.elem_y.ravel()])
    # Each centre takes the value of the mesh triangle it lies in (barycentric test).
    out = np.zeros(len(centres))
    p = mesh.nodes[mesh.triangles]
    lo, hi = p.min(axis=1), p.max(axis=1)
    for e in range(len(p)):
        near = np.all((centres >= lo[e] - 1e-9) & (centres <= hi[e] + 1e-9), axis=1)
        if not near.any():
            continue
        a, b, c = p[e]
        v0, v1, v2 = c - a, b - a, centres[near] - a
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
        d20, d21 = v2 @ v0, v2 @ v1
        denominator = d00 * d11 - d01 * d01
        u = (d11 * d20 - d01 * d21) / denominator
        v = (d00 * d21 - d01 * d20) / denominator
        hit = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
        idx = np.flatnonzero(near)[hit]
        out[idx] = values[e]
    return np.clip(out.reshape(problem.shape), problem.lower_bound, problem.upper_bound)
