# library/fe/q4_plane_stress.py — 2-D Q4 plane-stress finite element solver.
#
# This is ONE implementation of the physics, not the platform's definition of it.
# It owns everything that depends on the top88 conventions: the analytical 8×8
# element stiffness matrix, column-major DOF numbering, and the assemble-and-solve
# routine.  A different physics (3-D, thermal, a pyMOTO network) supplies its own
# module here and the engine never notices the difference.

import numpy as np
from scipy.ndimage import convolve  # image-style convolution filter
from scipy.sparse import coo_matrix  # sparse matrix in coordinate format
from scipy.sparse.linalg import spsolve  # sparse direct linear solver

# ── Finite element utilities ──────────────────────────────────────────────────

def element_stiffness(nu, dx=1.0, dy=1.0, thickness=1.0):
    """Stiffness matrix for one 4-node quad element (Q4) under plane stress.

    Computed by 2x2 Gauss integration of B^T D B over a dx x dy rectangle, with
    nodes ordered counter-clockwise from the bottom-left corner.  For dx == dy
    this reproduces the analytical unit-square matrix from the top88 MATLAB code
    to machine precision (see tests/test_fe.py), so replacing the hardcoded
    matrix with this one changed no result.

    A note on element size, because it is easy to get wrong: in 2-D the
    strain-displacement matrix scales as 1/h while the area integral scales as
    h^2, so a *uniform* rescaling leaves K unchanged.  Element size therefore
    does not affect a square-element 2-D model at all.  What does affect it is
    the element *aspect ratio* (dx != dy), which the hardcoded matrix silently
    ignored, and the out-of-plane thickness, which multiplies K linearly.

    This scale invariance is specific to 2-D.  In 3-D the volume integral scales
    as h^3 and K scales as h, so a 3-D solver must pass real element sizes.

    Parameters
    ----------
    nu : float
        Poisson's ratio (typically 0.3 for metals).
    dx, dy : float
        Element edge lengths.  Only their ratio affects the result.
    thickness : float
        Out-of-plane thickness; multiplies the whole matrix.

    Returns
    -------
    KE : np.ndarray, shape (8, 8)
        8 DOFs: 2 per corner node, x then y, counter-clockwise from bottom-left.
    """
    D = np.array([[1.0, nu, 0.0],
                  [nu, 1.0, 0.0],
                  [0.0, 0.0, (1.0 - nu) / 2.0]]) / (1.0 - nu ** 2)

    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))   # CCW from bottom-left
    gauss = (-1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0))

    KE = np.zeros((8, 8))
    for xi in gauss:
        for eta in gauss:
            # Shape function derivatives in the reference square, then mapped to
            # physical coordinates by the (diagonal, constant) Jacobian.
            dN_dxi = np.array([cx * (1 + cy * eta) / 4 for cx, cy in corners])
            dN_deta = np.array([cy * (1 + cx * xi) / 4 for cx, cy in corners])
            dN_dx, dN_dy = dN_dxi * (2.0 / dx), dN_deta * (2.0 / dy)

            B = np.zeros((3, 8))
            B[0, 0::2] = dN_dx      # exx
            B[1, 1::2] = dN_dy      # eyy
            B[2, 0::2] = dN_dy      # gxy
            B[2, 1::2] = dN_dx
            KE += B.T @ D @ B * (dx / 2.0) * (dy / 2.0) * thickness
    return KE


def element_dofs(problem):
    """Return an (nelx×nely) × 8 array mapping each element to its 8 global DOF indices.

    Each row corresponds to one element; the 8 columns are the DOF indices for
    the four corner nodes (2 DOFs each: x and y displacement).
    Column-major ordering matches the top88 MATLAB convention.
    """
    nely, nelx = problem.nely, problem.nelx
    nodenrs  = np.arange(1, (nelx+1)*(nely+1)+1).reshape((nely+1, nelx+1), order="F")
    edof_vec = (2 * nodenrs[:-1, :-1] + 1).reshape(nelx*nely, order="F")
    offsets  = np.array([0, 1, 2*nely+2, 2*nely+3, 2*nely, 2*nely+1, -2, -1])
    return edof_vec[:, None] + offsets[None, :] - 1


# ── Degree-of-freedom layout ──────────────────────────────────────────────────
#
# A BaseProblem describes geometry: node masks saying where the structure is
# held and where loads act.  Turning those into DOF indices and force vectors
# requires a numbering convention, and the convention belongs to the solver —
# so it lives here rather than in core.  Another solver (3-D, or a pyMOTO
# network) reads the same masks and applies its own numbering instead.


class Q4DofLayout:
    """Top88 column-major DOF numbering derived from a problem's node masks.

    Node ids run column-major (Fortran order) over the (nely+1, nelx+1) grid,
    and each node owns two consecutive DOFs: 2*node (x) and 2*node+1 (y).

    Attributes
    ----------
    ndof : int
        Total degrees of freedom, 2 per node.
    fixed_dofs, free_dofs : np.ndarray
        Constrained DOF indices, and their complement within arange(ndof).
    forces : list[tuple[float, np.ndarray]]
        One (weight, force_vector) pair per load case, in config order.
    """

    def __init__(self, problem, config):
        self.problem = problem
        self.load_cases = config.load_cases

        self.node_ids = np.arange(problem.nn).reshape(
            (problem.nely + 1, problem.nelx + 1), order="F"
        )
        self.ndof = 2 * problem.nn
        self.fixed_dofs = self._build_fixed_dofs()
        self.free_dofs = np.setdiff1d(np.arange(self.ndof), self.fixed_dofs)
        self.forces = [
            (lc.weight, self._force_vector(lc.Fmag, lc.Fa)) for lc in config.load_cases
        ]

    def _build_fixed_dofs(self):
        """Assemble the sorted array of constrained DOF indices from all node masks."""
        parts = []
        ids = self.node_ids[self.problem.fixed_nodes]
        if ids.size:
            parts.append(np.concatenate([2 * ids, 2 * ids + 1]))
        ids = self.node_ids[self.problem.fixed_x_nodes]
        if ids.size:
            parts.append(2 * ids)
        ids = self.node_ids[self.problem.fixed_y_nodes]
        if ids.size:
            parts.append(2 * ids + 1)
        if not parts:
            return np.array([], dtype=int)
        return np.unique(np.concatenate(parts))

    def _force_vector(self, magnitude, angle_degrees):
        """Build an ndof-long force vector for one load case.

        The load is split evenly across every node in every load region, so a
        load applied over a bolt ring does not scale with mesh refinement.
        """
        force = np.zeros(self.ndof)
        angle = np.deg2rad(angle_degrees)
        vector = magnitude * np.array([np.cos(angle), np.sin(angle)])
        for load_mask in self.problem.load_node_sets:
            nodes = self.node_ids[load_mask]
            per_node = vector / max(len(nodes), 1)
            for node in nodes:
                force[2 * node: 2 * node + 2] += per_node
        return force


def dof_layout(problem, config):
    """Return the Q4 DOF layout for a problem, building it once and caching it.

    solve_fea runs every iteration but the layout only depends on the geometry
    and the load cases, neither of which change during a run.
    """
    cached = getattr(problem, "_q4_dof_layout", None)
    if cached is None or cached.load_cases is not config.load_cases:
        cached = Q4DofLayout(problem, config)
        problem._q4_dof_layout = cached
    return cached


def solve_fea(problem, config, density, penal):
    """Assemble and solve the global FE system for all load cases.

    The SIMP material model maps density ρ to stiffness:
        E(ρ) = Emin + ρ^p × (E0 - Emin)
    where p (penal) penalises intermediate densities toward 0 or 1.
    Emin prevents singular (un-solvable) stiffness matrices in void regions.

    Parameters
    ----------
    penal : float
        SIMP exponent p.  It belongs to the calling method (a method parameter,
        not a scenario field); the level-set passes 1.0 for a linear model.

    Returns
    -------
    U          : (ndof × n_load_cases) displacement array
    ce         : (nely × nelx) weighted element compliance energy
    compliance : scalar total weighted compliance (the objective)
    """
    layout = dof_layout(problem, config)   # DOF indices + force vectors (cached)
    # Real element size: only the aspect ratio matters in 2-D, but passing it
    # makes non-square meshes correct and mirrors what a 3-D solver must do.
    KE     = element_stiffness(config.nu, problem.dx, problem.dy)
    edof   = element_dofs(problem)         # nelx*nely × 8 DOF index map

    # SIMP stiffness: flatten density to 1-D (column-major) then apply penalty.
    x         = density.reshape(-1, order="F")
    stiffness = config.Emin + x**penal * (config.E0 - config.Emin)

    # Assemble global sparse stiffness matrix K using triplet (COO) format.
    # iK, jK are row/col indices; sK are the values — all from the element contributions.
    iK = np.tile(edof, (1, 8)).ravel()
    jK = np.repeat(edof, 8, axis=1).ravel()
    sK = (KE.ravel(order="F")[None, :] * stiffness[:, None]).ravel()
    K  = coo_matrix((sK, (iK, jK)), shape=(layout.ndof, layout.ndof)).tocsc()
    K  = (K + K.T) * 0.5   # enforce exact symmetry (eliminates floating-point asymmetry)

    # Extract the free (unconstrained) sub-matrix for solving.
    Kff = K[layout.free_dofs][:, layout.free_dofs]

    # Solve K·U = F for each load case and accumulate weighted compliance.
    n_load_cases = len(layout.forces)
    U          = np.zeros((layout.ndof, n_load_cases))
    ce         = np.zeros((problem.nely, problem.nelx))
    compliance = 0.0
    for k, (weight, f) in enumerate(layout.forces):
        U[layout.free_dofs, k] = spsolve(Kff, f[layout.free_dofs])
        # Element compliance energy: ce_k[e] = u_e^T × KE × u_e
        ce_k = np.sum((U[edof, k] @ KE) * U[edof, k], axis=1).reshape(
            (problem.nely, problem.nelx), order="F"
        )
        C_k = float(np.sum(stiffness * ce_k.reshape(-1, order="F")))
        ce        += weight * ce_k
        compliance += weight * C_k

    return U, ce, compliance


def smooth_field(field, amount=0.15):
    """Apply a light neighbourhood-average smoothing to a 2-D field.
    Used by the level-set method to reduce noise.  amount=0 disables it."""
    if amount <= 0:
        return field
    kernel = np.array([[0.0, amount, 0.0],
                        [amount, 1.0, amount],
                        [0.0, amount, 0.0]])
    kernel /= np.sum(kernel)   # normalise so the sum of weights = 1
    return convolve(field, kernel, mode="nearest")
