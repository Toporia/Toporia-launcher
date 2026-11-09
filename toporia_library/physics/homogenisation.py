# toporia_library/physics/homogenisation.py — periodic unit cells and their effective elasticity (multiscale).
#
# The design domain is one cell of a periodic material, not a part.  What it is worth is its
# homogenised elasticity tensor C^H: the stiffness a large piece of the material has when the
# cell repeats in every direction.  Numerical homogenisation (energy form, as in
# E. Andreassen, C. S. Andreasen, "How to determine composite material properties using
# numerical homogenization", Comput. Mater. Sci. 83 (2014) 488-495):
#
#   1. unit test strains ε⁰ⁱ: in 2-D (xx, yy, xy), in 3-D (xx, yy, zz, yz, xz, xy), Voigt
#      notation with engineering shear; u⁰ⁱ_e is the displacement of element e's corners under
#      the uniform strain ε⁰ⁱ (u = ε⁰ⁱ x in element-local coordinates, since K_e ignores
#      rigid motion)
#   2. periodic boundary conditions: nodes on opposite faces of the cell are the same node,
#      one node is held to remove the rigid translation
#   3. the fluctuation χⁱ from K(ρ) χⁱ = fⁱ,   fⁱ = Σ_e K_e(ρ_e) u⁰ⁱ_e   (assembled periodically)
#   4. C^H_ij = (1/|Y|) Σ_e E(ρ_e) qᵢⱼ,e,   qᵢⱼ,e = (u⁰ⁱ − χⁱ)_eᵀ K_e⁰ (u⁰ʲ − χʲ)_e
#   5. ∂C^H_ij/∂ρ_e = (1/|Y|) E'(ρ_e) qᵢⱼ,e  — exact: the energy is stationary in χ, so no
#      adjoint solve is needed (the same argument as for compliance)
#
# K_e⁰ is the element matrix at unit Young's modulus (Q4 or H8, isotropic, the scenario's ν)
# and E(ρ) the material law.  The cell is the scenario's domain on its mesh; supports and loads
# of the scenario are not used (the test strains load the cell).
#
# Reference: J. M. Guedes, N. Kikuchi, CMAME 83 (1990) 143-198 (homogenisation for design);
# O. Sigmund, "Materials with prescribed constitutive parameters: an inverse homogenization
# problem", Int. J. Solids Struct. 31 (1994) 2313-2329.

import numpy as np

from toporia_core.framework.parts.physics import HOMOGENISED, HomogenisedPhysics, Physics


def _unit_strains(dims):
    """The symmetric strain tensors of the unit test strains, Voigt order with engineering shear."""
    if dims == 2:
        pairs = [(0, 0), (1, 1), (0, 1)]
    else:
        pairs = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
    strains = []
    for a, b in pairs:
        S = np.zeros((dims, dims))
        if a == b:
            S[a, a] = 1.0
        else:
            S[a, b] = S[b, a] = 0.5                 # engineering shear γ = 1
        strains.append(S)
    return strains


class _PeriodicCell(Physics, HomogenisedPhysics):
    """Shared machinery of the periodic unit-cell engines."""

    provides = (HOMOGENISED,)
    uses_interpolation = True
    element_order = "C"
    dims = ()

    def initialize(self, problem, settings, interpolation=None):
        from toporia_library.interpolations.simp import SIMP
        self.problem = problem
        self.material = interpolation if interpolation is not None else SIMP()
        self.shape = tuple(problem.shape)
        self.KE, corners = self._element(problem)                     # KE at unit E, corner local coordinates
        self.edof, n_nodes = self._periodic_dofs(problem)
        d = len(corners[0])
        self.ndof = d * n_nodes
        per = self.KE.shape[0]
        self.rows = np.repeat(self.edof, per, axis=1).ravel()
        self.cols = np.tile(self.edof, (1, per)).ravel()
        free = np.ones(self.ndof, bool)
        free[:d] = False                                              # node 0 held: no rigid translation
        self.free = np.flatnonzero(free)
        # u⁰ⁱ per element (the same for every element: same size, element-local coordinates)
        self.u0 = np.array([(np.asarray(corners) @ S.T).ravel() for S in _unit_strains(d)])   # (cases, per)
        self.cell_measure = float(np.prod([problem.Lx, problem.Ly] + ([problem.Lz] if problem.dims == 3 else [])))

    def solve(self, density):
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import splu
        scenario = self.problem.scenario
        E = self.material.stiffness(np.asarray(density).reshape(-1), scenario.E0, scenario.Emin)
        values = (self.KE.ravel()[None, :] * E[:, None]).ravel()
        K = coo_matrix((values, (self.rows, self.cols)), shape=(self.ndof, self.ndof)).tocsc()
        K = ((K + K.T) * 0.5)[self.free][:, self.free].tocsc()
        factor = splu(K)
        Ku0 = self.u0 @ self.KE                                       # (cases, per): K_e⁰ u⁰ⁱ
        displacements = []
        for case in range(len(self.u0)):
            force = np.zeros(self.ndof)
            np.add.at(force, self.edof, E[:, None] * Ku0[case][None, :])
            chi = np.zeros(self.ndof)
            chi[self.free] = factor.solve(force[self.free])
            displacements.append(self.u0[case][None, :] - chi[self.edof])           # (n_el, per)
        d = np.array(displacements)                                   # (cases, n_el, per)
        q = np.einsum("aep,pr,ber->abe", d, self.KE, d)               # qᵢⱼ,e at unit E
        C = np.einsum("abe,e->ab", q, E) / self.cell_measure
        return _HomogenisedState(np.asarray(density), E, q, 0.5 * (C + C.T))

    def stiffness_slope(self, state):
        scenario = self.problem.scenario
        return self.material.slope(state.density, scenario.E0, scenario.Emin)

    def homogenised(self, state):
        return state.C

    def homogenised_slope(self, state, i, j):
        slope = self.stiffness_slope(state).reshape(-1)
        return (slope * state.q[i, j] / self.cell_measure).reshape(self.shape)


class _HomogenisedState:
    """One solve: the density, E per element, qᵢⱼ,e at unit E, and C^H."""

    def __init__(self, density, E, q, C):
        self.density, self.E, self.q, self.C = density, E, q, C
        self.weights = [1.0]


class Q4PeriodicCell(_PeriodicCell):
    """A 2-D periodic unit cell (plane stress, Q4 elements): its homogenised elasticity tensor."""

    name = "q4_periodic"
    label = "2-D periodic unit cell (homogenisation)"
    order = 60
    dims = (2,)

    def _element(self, problem):
        from toporia_library.physics.q4_plane_stress import element_stiffness
        KE = element_stiffness(problem.scenario.nu, problem.dx, problem.dy)
        corners = [(0.0, 0.0), (problem.dx, 0.0), (problem.dx, problem.dy), (0.0, problem.dy)]
        return KE, corners

    def _periodic_dofs(self, problem):
        nely, nelx = problem.shape
        rows, cols = np.meshgrid(np.arange(nely), np.arange(nelx), indexing="ij")
        rows, cols = rows.ravel(), cols.ravel()                       # C order over (y, x)
        def node(r, c):
            return (r % nely) * nelx + (c % nelx)
        corners = [node(rows, cols), node(rows, cols + 1), node(rows + 1, cols + 1), node(rows + 1, cols)]
        edof = np.stack([2 * n + k for n in corners for k in range(2)], axis=1)
        return edof, nely * nelx


class H8PeriodicCell(_PeriodicCell):
    """A 3-D periodic unit cell (H8 bricks): its homogenised elasticity tensor."""

    name = "h8_periodic"
    label = "3-D periodic unit cell (homogenisation)"
    order = 61
    dims = (3,)

    def _element(self, problem):
        from toporia_library.physics.h8_solid import CORNERS, element_stiffness
        KE = element_stiffness(problem.scenario.nu, problem.dx, problem.dy, problem.dz)
        size = np.array([problem.dx, problem.dy, problem.dz])
        corners = [tuple((np.array(c) + 1) / 2 * size) for c in CORNERS]
        return KE, corners

    def _periodic_dofs(self, problem):
        from toporia_library.physics.h8_solid import CORNERS
        nelz, nely, nelx = problem.shape
        layers, rows, cols = (a.ravel() for a in np.meshgrid(np.arange(nelz), np.arange(nely), np.arange(nelx),
                                                             indexing="ij"))
        def node(k, r, c):
            return (k % nelz) * nely * nelx + (r % nely) * nelx + (c % nelx)
        corners = [node(layers + (cz + 1) // 2, rows + (cy + 1) // 2, cols + (cx + 1) // 2) for cx, cy, cz in CORNERS]
        edof = np.stack([3 * n + k for n in corners for k in range(3)], axis=1)
        return edof, nelz * nely * nelx
