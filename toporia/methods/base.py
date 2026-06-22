# methods/base.py — shared FEA solver and algorithm interface
#
# This file has two jobs:
#   1. Define OptimizationMethod: the abstract interface that every algorithm must
#      implement.  This guarantees that the runner and GUI can call any algorithm
#      through the same set of method names without knowing which one it is.
#   2. Provide the shared finite element solver (solve_fea) and utilities used by
#      both the density and level-set methods.

from abc import ABC, abstractmethod   # ABC = Abstract Base Class toolkit

import numpy as np
from scipy.ndimage import convolve                 # image-style convolution filter
from scipy.sparse import coo_matrix               # sparse matrix in coordinate format
from scipy.sparse.linalg import spsolve           # sparse direct linear solver


class OptimizationMethod(ABC):
    """Interface contract that every optimisation algorithm must satisfy.

    ABC (Abstract Base Class) enforces that any subclass MUST implement every
    method marked @abstractmethod.  If it doesn't, Python refuses to instantiate
    it.  The '...' (Ellipsis) body means "no default implementation".
    """

    @abstractmethod
    def initialize(self, problem, config): ...   # called once before the loop starts

    @abstractmethod
    def step(self): ...                          # advance by one iteration

    @abstractmethod
    def has_converged(self): ...                 # return True when the loop should stop

    @abstractmethod
    def get_density(self): ...                   # return current nely×nelx density array

    @abstractmethod
    def get_objective(self): ...                 # return current compliance value

    @abstractmethod
    def get_iteration(self): ...                 # return current iteration counter


# ── Finite element utilities ──────────────────────────────────────────────────

def element_stiffness(nu):
    """Compute the 8×8 stiffness matrix for one 4-node quad element (Q4).

    This is the standard analytical result for a unit square Q4 element under
    plane stress.  The formula comes directly from the top88 MATLAB code.
    nu is Poisson's ratio (typically 0.3 for metals).
    Returns KE: 8×8 array (8 DOFs per element: 2 per corner node).
    """
    A11 = np.array([[12,3,-6,-3],[3,12,3,0],[-6,3,12,-3],[-3,0,-3,12]])
    A12 = np.array([[-6,-3,0,3],[-3,-6,-3,-6],[0,-3,-6,3],[3,-6,3,-6]])
    B11 = np.array([[-4,3,-2,9],[3,-4,-9,4],[-2,-9,-4,-3],[9,4,-3,-4]])
    B12 = np.array([[2,-3,4,-9],[-3,2,9,-2],[4,9,2,3],[-9,-2,3,2]])
    return (1.0/(1.0-nu**2)/24.0
            * (np.block([[A11,A12],[A12.T,A11]]) + nu*np.block([[B11,B12],[B12.T,B11]])))


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


def solve_fea(problem, config, density, penal=None):
    """Assemble and solve the global FE system for all load cases.

    The SIMP material model maps density ρ to stiffness:
        E(ρ) = Emin + ρ^p × (E0 - Emin)
    where p (penal) penalises intermediate densities toward 0 or 1.
    Emin prevents singular (un-solvable) stiffness matrices in void regions.

    Returns
    -------
    U          : (ndof × n_load_cases) displacement array
    ce         : (nely × nelx) weighted element compliance energy
    compliance : scalar total weighted compliance (the objective)
    """
    penal = config.penal if penal is None else penal
    KE    = element_stiffness(config.nu)   # 8×8 element stiffness (same for all elements)
    edof  = element_dofs(problem)          # nelx*nely × 8 DOF index map

    # SIMP stiffness: flatten density to 1-D (column-major) then apply penalty.
    x         = density.reshape(-1, order="F")
    stiffness = config.Emin + x**penal * (config.E0 - config.Emin)

    # Assemble global sparse stiffness matrix K using triplet (COO) format.
    # iK, jK are row/col indices; sK are the values — all from the element contributions.
    iK = np.tile(edof, (1, 8)).ravel()
    jK = np.repeat(edof, 8, axis=1).ravel()
    sK = (KE.ravel(order="F")[None, :] * stiffness[:, None]).ravel()
    K  = coo_matrix((sK, (iK, jK)), shape=(problem.ndof, problem.ndof)).tocsc()
    K  = (K + K.T) * 0.5   # enforce exact symmetry (eliminates floating-point asymmetry)

    # Extract the free (unconstrained) sub-matrix for solving.
    Kff = K[problem.free_dofs][:, problem.free_dofs]

    # Solve K·U = F for each load case and accumulate weighted compliance.
    n_load_cases = len(problem.forces)
    U          = np.zeros((problem.ndof, n_load_cases))
    ce         = np.zeros((problem.nely, problem.nelx))
    compliance = 0.0
    for k, (weight, f) in enumerate(problem.forces):
        U[problem.free_dofs, k] = spsolve(Kff, f[problem.free_dofs])
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
