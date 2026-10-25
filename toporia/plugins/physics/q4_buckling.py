# plugins/physics/q4_buckling.py — 2-D Q4 plane stress plus linearised buckling.
#
# Q4PlaneStress (q4_plane_stress.py) with one more question answered, the
# BUCKLING feature of framework/parts/physics.py.  Nothing of the parent changes;
# this subclass only adds the geometric stiffness and the eigenproblem.
#
# Method (the formulation of Ferrari, Sigmund & Guest, SMO 63 (2021) 3045-3066,
# written here from its description, not from its code):
#
#   1. Prebuckling:     K u = f                      (the parent's solve)
#   2. Stress:          σ_e = S u_e                  (solid-material stress at the element centre)
#   3. Geometric K:     K_σ = Σ_e ρ_e^pσ · K_σe(σ_e), with
#                       K_σe = ∫ Gᵀ Σ(σ) G dA = σxx T_xx + σyy T_yy + τxy T_xy
#                       G maps element dofs to (u,x u,y v,x v,y); T_.. are constant 8×8 matrices.
#   4. Buckling:        (K + λ K_σ) φ = 0, equivalently  (−K_σ) φ = μ K φ  with μ = 1/λ.
#                       The buckling factors are the positive μ of largest value, inverted.
#
# K_σ is scaled with its own exponent pσ (a parameter).  In void elements the
# prebuckling displacements are large relative to the stiffness, which gives
# artificial buckling modes of the void; a higher exponent than the stiffness
# law's lets K_σ vanish faster than K there, so the modes disappear.
#
# Sensitivity, for K-normalised φ (φᵀ K φ = 1) and A = −K_σ:
#
#   μ = φᵀ A φ                    dμ = φᵀ dA φ − μ φᵀ dK φ
#   φᵀ dA φ  = explicit (through ρ^pσ)  +  through u (K_σ depends on u = K⁻¹ f)
#   through u:  with g = ∂(φᵀAφ)/∂u,  K a = g,  d(φᵀAφ) = −dE/dρ · aᵀ K_e u_e
#   dλ = −dμ / μ²
#
# The adjoint a solves a system with the same K as the prebuckling solve, so
# its factorisation is reused: one extra back-substitution per mode.
#
# Eigenvalues: scipy.sparse.linalg.eigsh on the pencil (−K_σ, K) for the largest
# algebraic μ.  K is positive definite, ARPACK factorises it once and applies
# its inverse in every step, which is shift-invert about zero for the pencil.
# Small systems use a dense solver, which is exact and not slower.
#
# Repeated eigenvalues are not differentiable; the response that uses this
# (responses/buckling.py) aggregates several modes so the sum is smooth.

import numpy as np
from scipy.linalg import eigh
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh, splu

from toporia.framework.params import Param
from toporia.framework.parts.physics import BUCKLING, ELASTIC_ENERGY, STRESS
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress, Q4Solution, _solve

#: Systems with fewer free degrees of freedom than this are solved densely.
_DENSE_LIMIT = 600


def geometric_stiffness_basis(dx=1.0, dy=1.0, thickness=1.0):
    """The three constant 8×8 matrices (T_xx, T_yy, T_xy) of the element geometric stiffness.

    K_σe = σxx T_xx + σyy T_yy + τxy T_xy for a stress that is constant over
    the element.  Same node and degree-of-freedom order as element_stiffness.
    2×2 Gauss integration is exact for these (bilinear shape functions give
    polynomial integrands of degree 2 per direction).
    """
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    gauss = (-1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0))
    unit_stress = [np.array([[1.0, 0.0], [0.0, 0.0]]),    # σxx
                   np.array([[0.0, 0.0], [0.0, 1.0]]),    # σyy
                   np.array([[0.0, 1.0], [1.0, 0.0]])]    # τxy
    basis = [np.zeros((8, 8)) for _ in range(3)]
    for xi in gauss:
        for eta in gauss:
            dN_dx = np.array([cx * (1 + cy * eta) / 4 for cx, cy in corners]) * (2.0 / dx)
            dN_dy = np.array([cy * (1 + cx * xi) / 4 for cx, cy in corners]) * (2.0 / dy)
            # Rows: ∂u/∂x, ∂u/∂y, ∂v/∂x, ∂v/∂y of the displacement field.
            G = np.zeros((4, 8))
            G[0, 0::2], G[1, 0::2] = dN_dx, dN_dy
            G[2, 1::2], G[3, 1::2] = dN_dx, dN_dy
            weight = (dx / 2.0) * (dy / 2.0) * thickness
            for T, s in zip(basis, unit_stress, strict=True):
                Sigma = np.kron(np.eye(2), s)    # the stress acts on the u and v gradients alike
                T += G.T @ Sigma @ G * weight
    return basis


class Q4BucklingSolution(Q4Solution):
    """A Q4 solution that also remembers its buckling analysis, so factors and sensitivities share it.

    A solution is made for one density and never changes, so what is computed
    from it (the factorisation of K, the geometric stiffness, the modes) is
    cached on it.
    """

    def __init__(self, base):
        super().__init__(base.density, base.stiffness, base.U, base.Kff, base.weights,
                         base.energies, base.compliances)
        self.lu = None                  # factorisation of Kff
        self.geometric = {}             # case -> (stress, assembled −K_σ on the free dofs)
        self.modes = {}                 # case -> (n requested, μ, φ on the free dofs)
        self.adjoints = {}              # (case, i) -> adjoint solution on all dofs


class Q4Buckling(Q4PlaneStress):
    """Linear elasticity as Q4PlaneStress, and the linearised buckling load factors of every load case."""

    name = "q4_buckling"
    label = "2-D Q4 with buckling (Toporia)"
    order = 20
    provides = (ELASTIC_ENERGY, STRESS, BUCKLING)
    params = (
        Param("p_sigma", 4.0, "Geometric stiffness exponent",
              "The geometric (stress) stiffness of an element is scaled by density^p. Keep it above "
              "the material law's exponent (3 for SIMP): then it vanishes faster than the stiffness "
              "in void and the artificial buckling modes of the void disappear.",
              min=1.0, max=10.0, step=0.5, decimals=1),
    )

    def initialize(self, problem, settings, interpolation=None):
        super().initialize(problem, settings, interpolation)
        self.p_sigma = float(settings.get("p_sigma", 4.0))
        self.basis = np.array(geometric_stiffness_basis(problem.dx, problem.dy))   # (3, 8, 8)
        # Row/column indices of the element matrices in the global matrix, for assembly.
        self._rows = np.tile(self.edof, (1, 8)).ravel()
        self._cols = np.repeat(self.edof, 8, axis=1).ravel()

    def solve(self, density):
        return Q4BucklingSolution(_solve(self.problem, density, self.material))

    # ── Geometric stiffness ───────────────────────────────────────────────────

    def _weights(self, state):
        """ρ^pσ per element (column-major) and its derivative with respect to ρ."""
        rho = state.density.reshape(-1, order="F")
        return rho ** self.p_sigma, self.p_sigma * rho ** (self.p_sigma - 1.0)

    def _minus_geometric(self, state, case):
        """−K_σ on the free dofs, as a sparse matrix; cached with the stress per case."""
        if case not in state.geometric:
            w, _ = self._weights(state)
            stress = state.U[self.edof, case] @ self.S.T                    # (n_el, 3) solid stress
            # Element matrix = ρ^pσ Σ_k σ_k T_k, as 64 values per element.
            element = -w[:, None] * (stress @ self.basis.reshape(3, 64))
            n = self.layout.ndof
            full = coo_matrix((element.ravel(), (self._rows, self._cols)), shape=(n, n)).tocsc()
            full = (full + full.T) * 0.5
            free = self.layout.free_dofs
            state.geometric[case] = (stress, full[free][:, free])
        return state.geometric[case][1]

    # ── Eigenproblem ──────────────────────────────────────────────────────────

    def _modes(self, state, case, n):
        """(μ, φ) of the (at most) n largest positive μ = 1/λ, μ descending, φ with φᵀ K φ = 1."""
        cached = state.modes.get(case)
        if cached is not None and cached[0] >= n:
            return cached[1][:n], cached[2][:, :n]
        A = self._minus_geometric(state, case)
        K = state.Kff
        size = K.shape[0]
        k = min(n, size - 2)
        if size <= _DENSE_LIMIT:
            values, vectors = eigh(A.toarray(), K.toarray(), subset_by_index=[size - k, size - 1])
            values, vectors = values[::-1], vectors[:, ::-1]
        else:
            # which="LA": the largest algebraic μ, the lowest positive buckling loads.
            # A fixed start vector, so the same design always gives the same bits (ARPACK would draw a random one).
            values, vectors = eigsh(A, k=k, M=K, which="LA", v0=np.ones(size))
            order = np.argsort(-values)
            values, vectors = values[order], vectors[:, order]
        keep = values > 1e-12 * max(values[0], 1e-300) if values[0] > 0 else np.zeros(len(values), bool)
        state.modes[case] = (n, values[keep], vectors[:, keep])
        return state.modes[case][1][:n], state.modes[case][2][:, :n]

    def buckling_factors(self, state, case, n):
        mu, _ = self._modes(state, case, n)
        return 1.0 / mu

    def _lu(self, state):
        if state.lu is None:
            state.lu = splu(state.Kff.tocsc())
        return state.lu

    def buckling_sensitivity(self, state, case, i):
        mu, phi = self._modes(state, case, i + 1)
        if i >= len(mu):
            raise IndexError(f"mode {i} does not exist: only {len(mu)} positive buckling factors")
        mu_i, mode = mu[i], np.zeros(self.layout.ndof)
        mode[self.layout.free_dofs] = phi[:, i]
        phi_e = mode[self.edof]                                             # (n_el, 8)
        stress = state.geometric[case][0] if case in state.geometric else None
        if stress is None:
            self._minus_geometric(state, case)
            stress = state.geometric[case][0]
        w, dw = self._weights(state)

        # c_k = φ_eᵀ T_k φ_e : how strongly each stress component stiffens or softens this mode.
        c = np.einsum("ea,kab,eb->ek", phi_e, self.basis, phi_e)
        # Explicit part of d(φᵀAφ)/dρ, A = −K_σ.
        explicit = -dw * np.sum(c * stress, axis=1)
        # Part through u: g = ∂(φᵀAφ)/∂u, assembled like the stress load, then one back-substitution.
        d_stress = -w[:, None] * c                                          # ∂(φᵀAφ)/∂σ_e
        g = np.zeros(self.layout.ndof)
        np.add.at(g, self.edof, d_stress @ self.S)
        free = self.layout.free_dofs
        adjoint = np.zeros_like(g)
        adjoint[free] = self._lu(state).solve(g[free])
        u_e = state.U[self.edof, case]
        through_u = -self._per_element(self.stiffness_slope(state)) * np.sum(
            (adjoint[self.edof] @ self.KE) * u_e, axis=1)
        # −μ φᵀ dK φ: the stiffness of the mode itself.
        stiffness_part = -mu_i * self._per_element(self.stiffness_slope(state)) * np.sum(
            (phi_e @ self.KE) * phi_e, axis=1)

        d_mu = self._field(explicit + through_u + stiffness_part)
        return -d_mu / mu_i ** 2
