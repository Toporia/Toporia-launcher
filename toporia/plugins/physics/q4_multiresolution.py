"""Nested Q4 displacement space over a finer density grid.

Independent aligned 2-D variant of Nguyen, Paulino, Song & Le, SMO 41 (2010)
525–539, doi:10.1007/s00158-009-0443-8, equations 10–15. The material is
constant on each fine cell; its stiffness contribution is integrated with
2x2 Gauss points rather than one centroid point per density cell.

For nested bilinear spaces, coarse displacement interpolation P is exact on
every fine element, hence K_c = P.T K_f(rho) P performs that subcell integral.
Only the coarse system is solved. Fine-cell energies supply the full density
gradient. Fine loads transfer by P.T, preserving virtual work. Fine Dirichlet
conditions are imposed as C u_c = 0, not snapped onto other nodes. Unit rows
are eliminated first; independent remaining constraints use a small saddle
block. This also preserves supports around fine-grid holes.

Scope: uniform nested 2-D grids; compliance/elastic energy only. Factor 1 is
the unchanged Q4 reference path. Larger integer factors require divisible
cell counts. No 3-D, stress, springs, adaptive/higher-order enrichment or
guarantee against artificially stiff fine features (QR-patterns). Always
reevaluate the final fine density with ordinary Q4 before trusting a gain.
"""

from dataclasses import dataclass

import numpy as np
from scipy.linalg import qr
from scipy.sparse import bmat, coo_matrix, csr_matrix, eye, kron
from scipy.sparse.linalg import splu

from toporia.framework.params import Param
from toporia.framework.parts.physics import ELASTIC_ENERGY, Physics

from .q4_plane_stress import Q4PlaneStress


def _linear_prolongation(n, factor):
    """Linear interpolation from n/factor+1 coarse nodes to n+1 fine nodes."""
    position = np.arange(n + 1) / factor
    left = np.minimum(np.floor(position).astype(int), n // factor - 1)
    fraction = position - left
    return coo_matrix((np.concatenate([1 - fraction, fraction]),
                       (np.tile(np.arange(n + 1), 2), np.concatenate([left, left + 1]))),
                      shape=(n + 1, n // factor + 1)).tocsr()


@dataclass
class MultiresolutionState:
    density: np.ndarray
    weights: list
    energies: list
    compliances: list
    U: np.ndarray
    coarse_U: np.ndarray
    coarse_stiffness: object


class Q4Multiresolution(Physics):
    """Fine-cell material, coarse bilinear displacement analysis and full adjoint."""

    name = "q4_multiresolution"
    label = "2-D Q4 multiresolution (nested grids)"
    provides = (ELASTIC_ENERGY,)
    uses_interpolation = True
    params = (
        Param("coarsening", 1, "Analysis coarsening factor",
              "1 is ordinary Q4. With 2 or more, each analysis cell spans this many fine "
              "density cells per axis; both fine cell counts must divide exactly. Fine "
              "features can be artificially stiff: verify the final design on fine Q4.",
              min=1, max=8),
    )
    reference = (
        'Independent aligned 2-D Galerkin/subcell-integration variant of T. H. Nguyen, '
        'G. H. Paulino, J. Song and C. H. Le, "A computational paradigm for multiresolution '
        'topology optimization (MTOP)", SMO 41 (2010) 525-539. Uses exact 2x2 integration '
        'per fine cell, not the centroid rule. Fine features can be artificially stiff; '
        'independent fine-Q4 reevaluation is essential. No stress, springs or 3-D. '
        'Papers: https://doi.org/10.1007/s00158-009-0443-8 '
        'https://doi.org/10.1007/s00158-018-2048-6'
    )

    def initialize(self, problem, settings, interpolation=None):
        value = settings.get("coarsening", 1)
        if not np.isfinite(value) or value != int(value) or not 1 <= value <= 8:
            raise ValueError("Analysis coarsening must be an integer from 1 to 8")
        self.coarsening = int(value)
        if len(problem.shape) != 2:
            raise ValueError("Q4 multiresolution currently requires a 2-D problem")
        if any(n % self.coarsening for n in problem.shape):
            raise ValueError(f"Fine mesh {problem.nelx}x{problem.nely} must be divisible by "
                             f"analysis coarsening {self.coarsening}; change the mesh resolution or factor")
        self.problem = problem
        self._reference = Q4PlaneStress()
        self._reference.initialize(problem, {}, interpolation)
        self.material, self.layout = self._reference.material, self._reference.layout
        self.edof, self.KE = self._reference.edof, self._reference.KE
        r = self.coarsening
        self.analysis_shape = (problem.nely // r, problem.nelx // r)
        self.analysis_dofs = 2 * (self.analysis_shape[0] + 1) * (self.analysis_shape[1] + 1)
        if r == 1:
            self.system_dofs = len(self.layout.free_dofs)
            return
        # Node ordering is x-major/y-minor, with interleaved x/y components,
        # exactly the ordering of the existing Q4 element/force utilities.
        scalar = kron(_linear_prolongation(problem.nelx, r),
                      _linear_prolongation(problem.nely, r), format="csr")
        self.prolongation = kron(scalar, eye(2, format="csr"), format="csr")
        self.prolongation.eliminate_zeros()
        conditions = self.prolongation[self.layout.fixed_dofs].tocsr()
        unit = np.diff(conditions.indptr) == 1
        fixed_coarse = np.unique(conditions[unit].indices)
        self._free = np.setdiff1d(np.arange(self.analysis_dofs), fixed_coarse)
        conditions = conditions[:, self._free].tocsr()
        conditions.eliminate_zeros()
        conditions = conditions[np.diff(conditions.indptr) > 0]
        if conditions.shape[0]:
            # Many fine constraints are redundant in the coarse space. QR
            # selects independent rows once, avoiding a singular KKT system.
            _, upper, pivots = qr(conditions.toarray().T, pivoting=True, mode="economic")
            diagonal = np.abs(np.diag(upper))
            tolerance = np.finfo(float).eps * max(conditions.shape) * np.max(diagonal)
            rank = int(np.sum(diagonal > tolerance))
            conditions = conditions[pivots[:rank]].tocsr()
        self._conditions = csr_matrix(conditions)
        self.system_dofs = len(self._free) + self._conditions.shape[0]
        if len(self._free) <= self._conditions.shape[0]:
            raise ValueError("Support conditions constrain the entire coarse displacement space; "
                             "use a finer analysis mesh")
        self._rows = np.tile(self.edof, (1, 8)).ravel()
        self._cols = np.repeat(self.edof, 8, axis=1).ravel()

    def solve(self, density):
        if self.coarsening == 1:
            return self._reference.solve(density)
        scenario = self.problem.scenario
        stiffness = self.material.stiffness(np.asarray(density).ravel(order="F"), scenario.E0, scenario.Emin)
        values = (stiffness[:, None] * self.KE.ravel(order="F")[None, :]).ravel()
        fine = coo_matrix((values, (self._rows, self._cols)),
                          shape=(self.layout.ndof, self.layout.ndof)).tocsc()
        coarse = (self.prolongation.T @ fine @ self.prolongation).tocsc()
        coarse = (coarse + coarse.T) * 0.5
        reduced = coarse[self._free][:, self._free]
        c = self._conditions
        system = bmat([[reduced, c.T], [c, None]], format="csc") if c.shape[0] else reduced
        factors = splu(system)
        forces = np.column_stack([force for _, force in self.layout.forces])
        rhs = (self.prolongation.T @ forces)[self._free]
        if c.shape[0]:
            rhs = np.vstack([rhs, np.zeros((c.shape[0], rhs.shape[1]))])
        coarse_u = np.zeros((self.analysis_dofs, forces.shape[1]))
        coarse_u[self._free] = factors.solve(rhs)[:len(self._free)]
        u = np.asarray(self.prolongation @ coarse_u)
        energies, compliances = [], []
        for case in range(u.shape[1]):
            local = u[self.edof, case]
            energy = np.sum((local @ self.KE) * local, axis=1)
            energies.append(energy.reshape(self.problem.shape, order="F"))
            compliances.append(float(stiffness @ energy))
        return MultiresolutionState(np.asarray(density), [w for w, _ in self.layout.forces],
                                    energies, compliances, u, coarse_u, coarse)

    def stiffness_slope(self, state):
        return self._reference.stiffness_slope(state)

    def compliance(self, state, case):
        return state.compliances[case]

    def strain_energy(self, state, case):
        return state.energies[case]
