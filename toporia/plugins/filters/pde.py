# plugins/filters/pde.py — PdeFilter (the PDE / Helmholtz density filter)
#
# Instead of averaging over a neighbour list, the design field is smoothed by
# solving a screened-Poisson (Helmholtz) equation with Neumann boundaries:
#
#       −r² ∇²ρ̄ + ρ̄ = ρ        on the domain,   ∂ρ̄/∂n = 0 on its boundary
#
# r = rmin / (2√3) is the relation of Lazarov & Sigmund (2011): it matches the PDE filter to
# the linear density filter of radius rmin in smoothing strength, so the two
# share one `rmin` parameter and can be
# compared directly.
#
# Discretisation, as in the top88 paper's PDE-filter section and DTU's top82.m:
#
#   A  = r²·K + M          the filter's own FE matrix on the same mesh, nodes
#                          as unknowns (Q4 in 2-D, H8 in 3-D; elements of size 1)
#   T  : element → node    each element hands ρ_e/2^d to each of its corners
#   ρ̄ = Tᵀ A⁻¹ T ρ         forward: element → node, solve, node → element
#
# A is factorised once in setup() (sparse LU) and reused every iteration.
# A and the product Tᵀ A⁻¹ T are symmetric, so backward() is the same three
# operations on the sensitivity — the exact adjoint.  A·1 = T·1 (the
# Neumann condition), so a constant field passes through unchanged, and
# 1ᵀ Tᵀ = (A·1)ᵀ makes the total volume exactly conserved.
#
# Assembly without loops: on a structured grid the element matrices are
# tensor products of 1-D ones, so the global matrices are Kronecker products
# of 1-D assembled matrices (axis order matches the field, C order):
#
#   M = ⊗ M1            K = Σ_axes  K1 on that axis ⊗ M1 on the others
#   M1 = [[2,1],[1,2]]/6    K1 = [[1,−1],[−1,1]]
#
# Passive/void elements are not treated specially, exactly as in the density
# filter: they are fixed by the physics layer after filtering.
#
# References:
#   B. S. Lazarov, O. Sigmund, "Filters in topology optimization based on
#     Helmholtz-type differential equations", IJNME 86 (2011) 765-781.
#   E. Andreassen et al., "Efficient topology optimization in MATLAB using 88
#     lines of code", SMO 43 (2011) 1-16 (PDE-filter section).
#   top82.m (DTU TopOpt group, open code), the PDE-filter version of top88.

import numpy as np
from scipy.sparse import csc_matrix, diags, kron
from scipy.sparse.linalg import splu

from toporia.framework.parts.filter import Filter
from toporia.plugins.shared_params import RMIN


def _chain(factors):
    """The Kronecker product of a list of sparse matrices, left to right."""
    out = factors[0]
    for factor in factors[1:]:
        out = kron(out, factor, format="csr")
    return out


def _axis_matrices(n):
    """1-D, for n elements of size 1 on n+1 nodes: (mass, stiffness, element→node averaging T1)."""
    # Assembling the 2x2 element matrices on overlapping node pairs gives these tridiagonals.
    mass_diag = np.full(n + 1, 4.0 / 6.0)
    mass_diag[[0, -1]] = 2.0 / 6.0
    M1 = diags([np.full(n, 1.0 / 6.0), mass_diag, np.full(n, 1.0 / 6.0)], [-1, 0, 1], format="csr")
    stiff_diag = np.full(n + 1, 2.0)
    stiff_diag[[0, -1]] = 1.0
    K1 = diags([np.full(n, -1.0), stiff_diag, np.full(n, -1.0)], [-1, 0, 1], format="csr")
    T1 = diags([np.ones(n), np.ones(n)], [0, -1], shape=(n + 1, n), format="csr")   # node i touches elements i-1, i
    return M1, K1, T1


class PdeFilter(Filter):
    """Helmholtz PDE density filter, solved on the design mesh.

    rmin: the radius of the equivalent linear density filter, in elements
    (the PDE's length scale is r = rmin / (2√3)).
    """

    name = "pde"
    reference = (
        'B. S. Lazarov and O. Sigmund, "Filters in topology optimization based on '
        'Helmholtz-type differential equations", Int. J. Numer. Meth. Eng. 86 (2011) 765-781; '
        'implemented as in the PDE-filter variant of top88 (Andreassen et al., Struct. '
        'Multidisc. Optim. 43 (2011) 1-16).'
        ' Papers: https://doi.org/10.1002/nme.3072 https://doi.org/10.1007/s00158-010-0594-7'
    )
    label = "PDE (Helmholtz) filter"
    use_when = (
        "Instead of the density filter on large or 3-D meshes, where a neighbourhood matrix gets "
        "expensive; it gives similar designs for the same radius."
    )
    dims = (2, 3)
    order = 11
    params = (RMIN,)

    def __init__(self, rmin=1.5):
        self.rmin = rmin

    def setup(self, problem, solver):
        """Assemble A and T from the mesh shape and factorise A once."""
        shape = tuple(problem.shape)
        r2    = (self.rmin / (2.0 * np.sqrt(3.0))) ** 2
        parts = [_axis_matrices(n) for n in shape]
        mass  = _chain([M1 for M1, _, _ in parts])
        stiff = 0
        for axis in range(len(shape)):
            stiff = stiff + _chain([parts[a][1] if a == axis else parts[a][0] for a in range(len(shape))])
        self._shape = shape
        self._T = (_chain([T1 for _, _, T1 in parts]) / 2.0 ** len(shape)).tocsr()
        self._lu = splu(csc_matrix(r2 * stiff + mass))

    def _apply(self, field):
        """Tᵀ A⁻¹ T field: element → node, solve, node → element (symmetric, so also the adjoint)."""
        nodal = self._lu.solve(self._T @ field.reshape(-1))
        return (self._T.T @ nodal).reshape(self._shape)

    def forward(self, x):
        return self._apply(x)

    def backward(self, x_in, sensitivity):
        return self._apply(sensitivity)
