# plugins/physics/h8_solid.py — 3-D linear elasticity on eight-node bricks (H8).
#
# The 3-D counterpart of q4_plane_stress.py, for a BoxProblem (a scenario with
# a depth, framework/problem/mesh.py).  Each element is a brick of dx × dy × dz
# with trilinear shape functions and three displacements per node; its 24 × 24
# stiffness matrix is integrated with 2 × 2 × 2 Gauss points, as in the 3-D
# code of Liu & Tovar (2014).  Unlike in 2-D, the element size matters: K
# scales with the element's length, so the real dx, dy, dz are used.
#
# The engine answers the same questions as the Q4 one (framework/parts/physics.py):
# compliance and strain energies, and the element stresses, adjoint solves and
# mutual energies a stress response needs — with six stress components
# (σxx, σyy, σzz, τyz, τxz, τxy) and the matching von Mises matrix.  So every
# response, filter, updater, schedule, variant and post-processor that works
# in 2-D works here unchanged.
#
# The linear solver: a direct sparse factorisation (SuperLU, kept for the
# adjoint solves) is exact and fast up to a few tens of thousands of
# unknowns.  Beyond that, conjugate gradients with smoothed-aggregation
# algebraic multigrid (the optional package pyamg), given the six rigid-body
# modes, scales to hundreds of thousands.  `linear_solver = auto` picks
# multigrid above `amg_above` unknowns when pyamg is installed.
#
# Elements and nodes are numbered in C order over (z, y, x); fields have the
# problem's shape (nelz, nely, nelx).
#
# Reference: K. Liu, A. Tovar, "An efficient 3D topology optimization code
# written in Matlab", Structural and Multidisciplinary Optimization 50 (2014)
# 1175-1196.

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

from toporia.framework.params import Param
from toporia.framework.parts.physics import ELASTIC_ENERGY, STRESS, Physics
from toporia.plugins.interpolations.simp import SIMP

#: Corners of the reference brick, in the element's node order.
CORNERS = ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
           (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))

#: σᵀ V σ is the squared von Mises stress, for Voigt (σxx, σyy, σzz, τyz, τxz, τxy).
VON_MISES_3D = np.array([[1.0, -0.5, -0.5, 0.0, 0.0, 0.0],
                         [-0.5, 1.0, -0.5, 0.0, 0.0, 0.0],
                         [-0.5, -0.5, 1.0, 0.0, 0.0, 0.0],
                         [0.0, 0.0, 0.0, 3.0, 0.0, 0.0],
                         [0.0, 0.0, 0.0, 0.0, 3.0, 0.0],
                         [0.0, 0.0, 0.0, 0.0, 0.0, 3.0]])


def elasticity_matrix(E, nu):
    """6 × 6 isotropic elasticity matrix, Voigt order with engineering shear strains."""
    lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = E / (2.0 * (1.0 + nu))
    D = np.zeros((6, 6))
    D[:3, :3] = lam
    D[np.arange(3), np.arange(3)] += 2.0 * mu
    D[np.arange(3, 6), np.arange(3, 6)] = mu
    return D


def strain_matrix(xi, eta, zeta, dx, dy, dz):
    """6 × 24 strain-displacement matrix at a point of the reference brick."""
    c = np.array(CORNERS, dtype=float)
    dN_dx = c[:, 0] * (1 + c[:, 1] * eta) * (1 + c[:, 2] * zeta) / 8 * (2.0 / dx)
    dN_dy = c[:, 1] * (1 + c[:, 0] * xi) * (1 + c[:, 2] * zeta) / 8 * (2.0 / dy)
    dN_dz = c[:, 2] * (1 + c[:, 0] * xi) * (1 + c[:, 1] * eta) / 8 * (2.0 / dz)
    B = np.zeros((6, 24))
    B[0, 0::3] = dN_dx
    B[1, 1::3] = dN_dy
    B[2, 2::3] = dN_dz
    B[3, 1::3], B[3, 2::3] = dN_dz, dN_dy        # γyz
    B[4, 0::3], B[4, 2::3] = dN_dz, dN_dx        # γxz
    B[5, 0::3], B[5, 1::3] = dN_dy, dN_dx        # γxy
    return B


def element_stiffness(nu, dx=1.0, dy=1.0, dz=1.0):
    """24 × 24 stiffness of one brick at unit Young's modulus, 2 × 2 × 2 Gauss points."""
    D = elasticity_matrix(1.0, nu)
    g = 1.0 / np.sqrt(3.0)
    KE = np.zeros((24, 24))
    for xi in (-g, g):
        for eta in (-g, g):
            for zeta in (-g, g):
                B = strain_matrix(xi, eta, zeta, dx, dy, dz)
                KE += B.T @ D @ B * (dx * dy * dz / 8.0)
    return 0.5 * (KE + KE.T)


def element_stress_matrix(E0, nu, dx=1.0, dy=1.0, dz=1.0):
    """6 × 24 matrix from an element's displacements to its stress at the centre, solid material."""
    return elasticity_matrix(E0, nu) @ strain_matrix(0.0, 0.0, 0.0, dx, dy, dz)


def element_dofs(problem):
    """(n_elements, 24) global DOF indices, elements in C order over (z, y, x)."""
    nelz, nely, nelx = problem.shape
    node_ids = np.arange(problem.nn).reshape((nelz + 1, nely + 1, nelx + 1))
    k, j, i = np.meshgrid(np.arange(nelz), np.arange(nely), np.arange(nelx), indexing="ij")
    corners = []
    for cx, cy, cz in CORNERS:
        corners.append(node_ids[k + (cz > 0), j + (cy > 0), i + (cx > 0)].ravel())
    nodes = np.stack(corners, axis=1)                        # (n_elements, 8)
    return (3 * nodes[:, :, None] + np.arange(3)).reshape(len(nodes), 24)


class H8DofLayout:
    """Three DOFs per node (x, y, z), supports and load vectors from a BoxProblem's node masks."""

    def __init__(self, problem):
        self.problem = problem
        self.node_ids = np.arange(problem.nn).reshape(tuple(n + 1 for n in problem.shape))
        self.ndof = 3 * problem.nn
        parts = [3 * self.node_ids[problem.fixed_nodes][:, None] + np.arange(3)]
        for axis, mask in enumerate((problem.fixed_x_nodes, problem.fixed_y_nodes,
                                     getattr(problem, "fixed_z_nodes", None))):
            if mask is not None:
                parts.append(3 * self.node_ids[mask][:, None] + axis)
        self.fixed_dofs = np.unique(np.concatenate([p.ravel() for p in parts]).astype(int))
        self.free_dofs = np.setdiff1d(np.arange(self.ndof), self.fixed_dofs)
        self.forces = [(case.weight, self._force(case)) for case in problem.scenario.load_cases]

    def _force(self, case):
        """The load case spread over every load region, each region carrying the full magnitude."""
        a, e = np.deg2rad(case.Fa), np.deg2rad(getattr(case, "Fe", 0.0))
        vector = case.Fmag * np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
        layers = getattr(self.problem, "layer_weights", None)
        force = np.zeros(self.ndof)
        for mask in self.problem.load_node_sets:
            k = np.nonzero(mask)[0]                          # the layer of every loaded node
            share = layers[k] if layers is not None else np.ones(len(k))
            share = share / share.sum()
            nodes = self.node_ids[mask]
            for axis in range(3):
                np.add.at(force, 3 * nodes + axis, share * vector[axis])
        return force


def rigid_body_modes(problem, free):
    """The six rigid-body displacement fields at the free DOFs: multigrid's near-null space."""
    x, y, z = (np.asarray(c, dtype=float).ravel() for c in (problem.node_x, problem.node_y, problem.node_z))
    modes = np.zeros((3 * len(x), 6))
    for axis in range(3):
        modes[axis::3, axis] = 1.0
    modes[0::3, 3], modes[1::3, 3] = -y, x                  # rotation about z
    modes[1::3, 4], modes[2::3, 4] = -z, y                  # rotation about x
    modes[0::3, 5], modes[2::3, 5] = z, -x                  # rotation about y
    return modes[free]


class H8Solution:
    """One solve: density, stiffness per element, displacements, the linear solver, energies, compliances."""

    def __init__(self, density, stiffness, U, solve_free, weights, energies, compliances):
        self.density, self.stiffness, self.U = density, stiffness, U
        self.solve_free = solve_free          # solves K_ff x = b again (adjoints) with the same factorisation
        self.weights, self.energies, self.compliances = weights, energies, compliances


class H8Solid(Physics):
    """Linear elasticity in 3-D on eight-node bricks, any material law, direct or multigrid solver."""

    name = "h8_solid"
    label = "3-D H8 bricks (Toporia)"
    order = 20
    dims = (3,)
    provides = (ELASTIC_ENERGY, STRESS)
    uses_interpolation = True
    von_mises_matrix = VON_MISES_3D
    params = (
        Param("linear_solver", "auto", "Linear solver",
              "Direct: exact sparse factorisation, best for small meshes. Multigrid: conjugate gradients "
              "with algebraic multigrid (needs pyamg), for large ones. Auto: multigrid above the size below.",
              choices=(("auto", "Auto"), ("direct", "Direct"), ("amg", "Multigrid (pyamg)"))),
        Param("amg_above", 60000, "Multigrid above",
              "With Auto, the number of unknowns above which multigrid is used.", min=0, max=100_000_000),
        Param("amg_tol", 1e-8, "Multigrid tolerance", "Relative residual the iterative solver stops at.",
              min=1e-14, max=1e-2, step=1e-8, decimals=12),
    )

    def initialize(self, problem, settings, interpolation=None):
        if getattr(problem, "dims", 2) != 3:
            raise ValueError("the H8 engine needs a 3-D problem: give the scenario a depth Lz > 0")
        scenario = problem.scenario
        self.problem = problem
        self.material = interpolation if interpolation is not None else SIMP()
        self.layout = H8DofLayout(problem)
        self.edof = element_dofs(problem)
        self.KE = element_stiffness(scenario.nu, problem.dx, problem.dy, problem.dz)
        self.S = element_stress_matrix(scenario.E0, scenario.nu, problem.dx, problem.dy, problem.dz)
        self.shape = problem.shape
        self.iK = np.repeat(self.edof, 24, axis=1).ravel()
        self.jK = np.tile(self.edof, (1, 24)).ravel()
        n_free = len(self.layout.free_dofs)
        choice = settings.get("linear_solver", "auto")
        if choice == "amg" or (choice == "auto" and n_free > settings.get("amg_above", 60000)):
            try:
                import pyamg  # noqa: F401
                self.use_amg = True
            except ImportError:
                if choice == "amg":
                    raise ImportError("the multigrid solver needs pyamg: pip install pyamg") from None
                self.use_amg = False
        else:
            self.use_amg = False
        self.amg_tol = settings.get("amg_tol", 1e-8)
        if self.use_amg:
            self.modes = rigid_body_modes(problem, self.layout.free_dofs)

    def _factorise(self, Kff):
        """A function solving K_ff x = b: an LU factorisation, or multigrid-preconditioned CG."""
        if not self.use_amg:
            lu = splu(Kff.tocsc())
            return lu.solve
        import pyamg
        hierarchy = pyamg.smoothed_aggregation_solver(Kff.tocsr(), B=self.modes, symmetry="hermitian")

        def solve(b):
            return hierarchy.solve(b, tol=self.amg_tol, accel="cg", maxiter=500)
        return solve

    def solve(self, density):
        scenario, layout = self.problem.scenario, self.layout
        stiffness = self.material.stiffness(density.reshape(-1), scenario.E0, scenario.Emin)
        sK = (self.KE.ravel()[None, :] * stiffness[:, None]).ravel()
        K = coo_matrix((sK, (self.iK, self.jK)), shape=(layout.ndof, layout.ndof)).tocsr()
        free = layout.free_dofs
        solve_free = self._factorise(K[free][:, free])
        U = np.zeros((layout.ndof, len(layout.forces)))
        energies, compliances = [], []
        for case, (_, force) in enumerate(layout.forces):
            U[free, case] = solve_free(force[free])
            Ue = U[self.edof, case]
            energy = np.sum((Ue @ self.KE) * Ue, axis=1)
            energies.append(energy.reshape(self.shape))
            compliances.append(float(np.sum(stiffness * energy)))
        return H8Solution(density, stiffness, U, solve_free, [w for w, _ in layout.forces], energies, compliances)

    def stiffness_slope(self, state):
        scenario = self.problem.scenario
        return self.material.slope(state.density, scenario.E0, scenario.Emin)

    def compliance(self, state, case):
        return state.compliances[case]

    def strain_energy(self, state, case):
        return state.energies[case]

    def element_stress(self, state, case):
        return (state.U[self.edof, case] @ self.S.T).reshape(self.shape + (6,))

    def stress_load(self, state, case, stress_sensitivity):
        per_element = stress_sensitivity.reshape(-1, 6) @ self.S
        load = np.zeros(self.layout.ndof)
        np.add.at(load, self.edof, per_element)
        return load

    def adjoint(self, state, load):
        free = self.layout.free_dofs
        solution = np.zeros_like(load)
        solution[free] = state.solve_free(load[free])
        return solution

    def mutual_energy(self, state, case, adjoint):
        return np.sum((adjoint[self.edof] @ self.KE) * state.U[self.edof, case], axis=1).reshape(self.shape)
