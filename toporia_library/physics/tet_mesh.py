# toporia_library/physics/tet_mesh.py — a tetrahedral mesh that follows 3-D holes, and linear tetrahedra.
#
# 3-D Delaunay meshes of points on curved surfaces are full of slivers: nearly flat
# tetrahedra whose stiffness matrices blow up.  This mesh is built so that it has none:
#
#   grid       nodes on a regular grid of spacing ≈ h fitted to the domain (an exact number
#              of steps along each axis), every cube split into the six tetrahedra around
#              its main diagonal (the Kuhn / Freudenthal split), which is conforming across
#              neighbouring cubes and has no slivers
#   snapping   every node within 0.4 h of a void surface (a hole through the depth, or a
#              sphere, cylinder or box void object) is moved onto it by Newton steps on the
#              surface's implicit function φ (φ < 0 inside the void):
#                  p ← p − φ(p) ∇φ / |∇φ|²
#              a move that would invert or flatten a tetrahedron (its volume falling below a
#              tenth of the original) is undone, so the mesh stays valid
#   cutting    tetrahedra whose centroid lies in a void (φ < 0, or a void element of the
#              structured problem for shapes without an implicit function) are removed; those
#              in forced-solid material are kept and fixed
#
# so the boundary follows a curved hole to second order in h instead of in cubic steps.
# Each tetrahedron is a linear (constant-strain) element:
#
#     N_i = a_i + b_i x + c_i y + d_i z,  B = ∂N/∂x arranged in Voigt order (6 × 12),
#     K_e = V_e Bᵀ D B,  D the isotropic 3-D elasticity matrix (E = 1, the material law scales it)
#
# Supports and loads come from the meshed problem's node masks, as in 2-D (t3_mesh.py).
#
# Reference: H. W. Kuhn (1960) and H. Freudenthal (1942) for the simplex split; snapping
# a background mesh to an implicit boundary as in body-fitted meshing (e.g. the "snap to
# boundary" step of octree mesh generators); constant-strain tetrahedra as in Zienkiewicz &
# Taylor, The Finite Element Method, vol. 1.

from dataclasses import dataclass
from itertools import permutations

import numpy as np


@dataclass
class TetMesh:
    """Nodes, tetrahedra and what lies on them."""
    nodes: np.ndarray        # (n, 3) in mm
    tets: np.ndarray         # (e, 4) node indices, positive orientation
    volumes: np.ndarray      # (e,)
    centroids: np.ndarray    # (e, 3)
    passive: np.ndarray      # (e,) bool: forced solid
    fixed: np.ndarray        # fixed DOF indices
    forces: list             # one (3n,) vector per load case
    weights: np.ndarray

    @property
    def areas(self):
        """The cell measures, under the name the 2-D mesh uses (volumes in 3-D)."""
        return self.volumes

    @property
    def triangles(self):
        """The cells, under the name the 2-D mesh uses (tetrahedra in 3-D)."""
        return self.tets


# ── Implicit functions of the void shapes (φ < 0 inside) ──────────────────────

def void_functions(problem):
    """φ(points) for every hole and every sphere, cylinder or box void of a 3-D problem."""
    from toporia_core.framework.problem.spatial import local_coordinates
    scenario, functions = problem.scenario, []
    for hole in scenario.holes:
        if hole.r_void > 0:
            cx, cy, r = hole.cx, hole.cy, hole.r_void
            functions.append(lambda p, cx=cx, cy=cy, r=r: np.hypot(p[:, 0] - cx, p[:, 1] - cy) - r)
    for obj in scenario.regions or ():
        if obj.get("role") != "void" or obj.get("shape") not in ("sphere", "cylinder", "box") or obj.get("extrusion"):
            continue
        size = np.asarray(obj["size"], float)

        def phi(p, obj=obj, size=size):
            local = local_coordinates(obj, p)
            if obj["shape"] == "sphere":
                semi = size / 2
                return (np.linalg.norm(local / semi, axis=-1) - 1.0) * float(np.min(semi))
            if obj["shape"] == "cylinder":
                semi = size[:2] / 2
                radial = (np.linalg.norm(local[:, :2] / semi, axis=-1) - 1.0) * float(np.min(semi))
                return np.maximum(radial, np.maximum(-local[:, 2], local[:, 2] - size[2]))
            outside = np.maximum(np.maximum(-local, local - size), 0.0)
            inside = np.minimum(np.max(np.maximum(-local, local - size), axis=-1), 0.0)
            return np.linalg.norm(outside, axis=-1) + inside
        functions.append(phi)
    return functions


def _phi_min(functions, points):
    return np.min([f(points) for f in functions], axis=0) if functions else np.full(len(points), np.inf)


# ── The mesh ──────────────────────────────────────────────────────────────────

def kuhn_tets(shape):
    """The six tetrahedra of every cube of a (nx, ny, nz) grid of cubes, as node indices of the grid."""
    nx, ny, nz = shape
    index = np.arange((nx + 1) * (ny + 1) * (nz + 1)).reshape(nx + 1, ny + 1, nz + 1)
    corner = index[:-1, :-1, :-1].ravel()
    steps = np.array([(ny + 1) * (nz + 1), nz + 1, 1])            # +x, +y, +z in flat indices
    tets = []
    for order in permutations(range(3)):
        a, b = steps[order[0]], steps[order[0]] + steps[order[1]]
        tets.append(np.stack([corner, corner + a, corner + b, corner + steps.sum()], axis=1))
    return np.concatenate(tets)


def _volumes(nodes, tets):
    p = nodes[tets]
    return np.einsum("ij,ij->i", np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), p[:, 3] - p[:, 0]) / 6.0


def _snap(nodes, tets, functions, h):
    """Move nodes near void surfaces onto them, undoing moves that would spoil a tetrahedron."""
    if not functions:
        return nodes
    original = _volumes(nodes, tets)
    moved = nodes.copy()
    phi = _phi_min(functions, moved)
    near = np.abs(phi) < 0.4 * h
    for _ in range(3):                                        # Newton steps onto φ = 0
        p = moved[near]
        if not len(p):
            break
        value = _phi_min(functions, p)
        eps = 1e-4 * h
        gradient = np.stack([(_phi_min(functions, p + eps * e) - _phi_min(functions, p - eps * e)) / (2 * eps)
                             for e in np.eye(3)], axis=1)
        moved[near] = p - (value / np.maximum(np.sum(gradient ** 2, axis=1), 1e-12))[:, None] * gradient
    for _ in range(10):                                       # undo moves that spoil a tetrahedron
        bad = _volumes(moved, tets) < 0.1 * original
        if not bad.any():
            break
        culprits = np.unique(tets[bad])
        moved[culprits] = nodes[culprits]
    return moved


def _cell_of(problem, points):
    """The structured element (layer, row, column) under each point."""
    column = np.clip((points[:, 0] / problem.dx).astype(int), 0, problem.nelx - 1)
    row = np.clip((points[:, 1] / problem.dy).astype(int), 0, problem.nely - 1)
    layer = np.clip((points[:, 2] / problem.dz).astype(int), 0, problem.nelz - 1)
    return layer, row, column


def build_tet_mesh(problem, size):
    """The tetrahedral mesh of a 3-D problem, with cubes of about `size` mm cut into six tetrahedra."""
    if problem.dims != 3:
        raise ValueError("The tetrahedral mesh is 3-D")
    extent = np.array([problem.Lx, problem.Ly, problem.Lz], float)
    counts = np.maximum(1, np.round(extent / float(size)).astype(int))
    axes = [np.linspace(0.0, L, n + 1) for L, n in zip(extent, counts, strict=True)]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    tets = kuhn_tets(tuple(counts))
    flip = _volumes(grid, tets) < 0                           # half the split comes out mirrored
    tets[flip] = tets[flip][:, [0, 2, 1, 3]]
    h = float(np.min(extent / counts))
    functions = void_functions(problem)
    nodes = _snap(grid, tets, functions, h)
    volumes = _volumes(nodes, tets)
    centroids = nodes[tets].mean(axis=1)
    keep = volumes > 1e-12 * h ** 3
    keep &= _phi_min(functions, centroids) > 0
    # The structured problem's void elements are a staircase of the same holes: near an
    # implicit void they are left to φ, elsewhere (other void shapes) they still cut.
    staircase = problem.void_elements.copy()
    if functions:
        cells = np.stack([problem.elem_x, problem.elem_y, problem.elem_z], axis=-1).reshape(-1, 3)
        reach = float(np.linalg.norm([problem.dx, problem.dy, problem.dz]))
        staircase &= ~(_phi_min(functions, cells) < reach).reshape(staircase.shape)
    keep &= ~staircase[_cell_of(problem, centroids)]
    tets, volumes, centroids = tets[keep], volumes[keep], centroids[keep]
    used = np.unique(tets)
    renumber = -np.ones(len(nodes), int)
    renumber[used] = np.arange(len(used))
    nodes, tets = nodes[used], renumber[tets]
    passive = problem.passive_elements[_cell_of(problem, centroids)]
    fixed, forces, weights = _boundary_conditions(problem, nodes)
    return TetMesh(nodes, tets, volumes, centroids, passive, fixed, forces, weights)


def _nearest(nodes, point):
    return int(np.argmin(np.sum((nodes - point) ** 2, axis=1)))


def _boundary_conditions(problem, nodes):
    """Supports and per-load-case forces on the tetrahedral mesh, from the problem's node masks."""
    grid = np.stack([problem.node_x, problem.node_y, problem.node_z], axis=-1)
    fixed = []
    for mask, components in ((problem.fixed_nodes, (0, 1, 2)), (problem.fixed_x_nodes, (0,)),
                             (problem.fixed_y_nodes, (1,)), (problem.fixed_z_nodes, (2,))):
        for point in grid[mask]:
            node = _nearest(nodes, point)
            fixed += [3 * node + c for c in components]
    forces, weights = [], []
    for index, case in enumerate(problem.scenario.load_cases):
        force = np.zeros(3 * len(nodes))
        regional = getattr(problem, "region_loads", None)
        if regional:
            entries = [(mask, vector) for case_index, mask, vector in regional if case_index == index]
        else:
            a, e = np.deg2rad(case.Fa), np.deg2rad(getattr(case, "Fe", 0.0))
            vector = case.Fmag * np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
            entries = [(mask, vector) for mask in problem.load_node_sets]
        for mask, vector in entries:
            points = grid[mask]
            for point in points:
                node = _nearest(nodes, point)
                force[3 * node: 3 * node + 3] += np.resize(np.asarray(vector, float), 3) / max(len(points), 1)
        forces.append(force)
        weights.append(case.weight)
    return np.unique(np.array(fixed, int)), forces, np.array(weights, float)


# ── The element ───────────────────────────────────────────────────────────────

def tet_element_matrices(mesh, nu):
    """K_e = V_e Bᵀ D B of every tetrahedron at unit Young's modulus, (e, 12, 12)."""
    from toporia_library.physics.h8_solid import elasticity_matrix
    D = elasticity_matrix(1.0, nu)
    p = mesh.nodes[mesh.tets]                                         # (e, 4, 3)
    M = np.concatenate([np.ones((len(p), 4, 1)), p], axis=2)          # rows [1 x y z]
    gradients = np.linalg.inv(M)[:, 1:, :]                            # (e, 3, 4): ∂N_i/∂(x, y, z)
    B = np.zeros((len(p), 6, 12))
    gx, gy, gz = gradients[:, 0], gradients[:, 1], gradients[:, 2]
    B[:, 0, 0::3], B[:, 1, 1::3], B[:, 2, 2::3] = gx, gy, gz
    B[:, 3, 0::3], B[:, 3, 1::3] = gy, gx                            # γ_xy
    B[:, 4, 1::3], B[:, 4, 2::3] = gz, gy                            # γ_yz
    B[:, 5, 0::3], B[:, 5, 2::3] = gz, gx                            # γ_xz
    return np.einsum("eki,kl,elj->eij", B, D, B) * mesh.volumes[:, None, None]


def tet_dofs(mesh):
    """(e, 12) DOF indices: x, y and z of each corner."""
    t = mesh.tets
    return np.stack([3 * t[:, i] + c for i in range(4) for c in range(3)], axis=1)


def tets_on_grid(problem, mesh, values):
    """Tetrahedron values sampled at the structured grid's element centres (for the engine's record)."""
    centres = np.stack([problem.elem_x, problem.elem_y, problem.elem_z], axis=-1).reshape(-1, 3)
    out = np.zeros(len(centres))
    p = mesh.nodes[mesh.tets]
    lo, hi = p.min(axis=1), p.max(axis=1)
    inverse = np.linalg.inv(np.concatenate([np.ones((len(p), 4, 1)), p], axis=2))   # barycentric map
    for e in range(len(p)):
        near = np.all((centres >= lo[e] - 1e-9) & (centres <= hi[e] + 1e-9), axis=1)
        if not near.any():
            continue
        q = np.concatenate([np.ones((int(near.sum()), 1)), centres[near]], axis=1)
        weights = q @ inverse[e]
        hit = np.all(weights >= -1e-9, axis=1)
        out[np.flatnonzero(near)[hit]] = values[e]
    return np.clip(out.reshape(problem.shape), problem.lower_bound, problem.upper_bound)


def solid_surface(mesh, values, level=0.5):
    """The boundary triangles (mm) of the tetrahedra at or above `level`: faces that only one of them has."""
    solid = mesh.tets[values >= level]
    faces = np.concatenate([solid[:, [0, 2, 1]], solid[:, [0, 1, 3]], solid[:, [1, 2, 3]], solid[:, [0, 3, 2]]])
    key = np.sort(faces, axis=1)
    _, first, counts = np.unique(key, axis=0, return_index=True, return_counts=True)
    boundary = faces[first[counts == 1]]
    return mesh.nodes[boundary]
