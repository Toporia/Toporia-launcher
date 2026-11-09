# toporia_library/physics/q4_orthotropic.py — plane stress with a fibre direction per element.
#
# Several fields per element (Wave 5).  Every element is a fibre-reinforced lamina: stiff
# along its fibres (E1 = E0), soft across them (E2), with shear modulus G12 and Poisson's
# ratio ν12.  Its fibres point at the angle θ_e of the field "angle" (radians, from +x),
# which the representation fibre_angle provides.  Rotating the lamina's stiffness to θ, in
# Tsai and Pagano's invariant form,
#
#     Q̄11 = U1 + U2 cos2θ + U3 cos4θ        Q̄22 = U1 − U2 cos2θ + U3 cos4θ
#     Q̄12 = U4 − U3 cos4θ                   Q̄66 = U5 − U3 cos4θ
#     Q̄16 = ½U2 sin2θ + U3 sin4θ            Q̄26 = ½U2 sin2θ − U3 sin4θ
#
# makes the element matrix a fixed combination of five matrices,
#
#     K_e(θ) = K0 + cos2θ K1 + sin2θ K2 + cos4θ K3 + sin4θ K4,      K_j = ∫ Bᵀ D_j B
#
# so it is assembled exactly for any angle and its derivative is closed-form:
#
#     ∂K_e/∂θ = −2 sin2θ K1 + 2 cos2θ K2 − 4 sin4θ K3 + 4 cos4θ K4
#
# The density scales the lamina like SIMP: E_e(ρ) from the material law, relative to E0.
# It answers the elastic-energy questions (compliance, with exact density and angle
# sensitivities); stresses of a rotated lamina are not provided.  Without an angle field
# (a density-only representation) every fibre points along +x.
#
# Reference: S. W. Tsai, N. J. Pagano, "Invariant properties of composite materials" (1968);
# continuous fibre-angle optimisation as in J. Stegmann, E. Lund, IJNME 62 (2005) and
# Nomura et al., IJNME 101 (2015) 571-605.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.physics import ELASTIC_ENERGY

from .q4_plane_stress import Q4PlaneStress, Q4Solution, dof_layout, element_dofs


def lamina_invariants(E1, E2, G12, nu12):
    """Tsai–Pagano invariants U1 … U5 of an orthotropic lamina in plane stress."""
    nu21 = nu12 * E2 / E1
    d = 1.0 - nu12 * nu21
    Q11, Q22, Q12, Q66 = E1 / d, E2 / d, nu12 * E2 / d, G12
    return ((3 * Q11 + 3 * Q22 + 2 * Q12 + 4 * Q66) / 8, (Q11 - Q22) / 2, (Q11 + Q22 - 2 * Q12 - 4 * Q66) / 8,
            (Q11 + Q22 + 6 * Q12 - 4 * Q66) / 8, (Q11 + Q22 - 2 * Q12 + 4 * Q66) / 8)


def constitutive_parts(E1, E2, G12, nu12):
    """D0 … D4 with D(θ) = D0 + cos2θ D1 + sin2θ D2 + cos4θ D3 + sin4θ D4 (Voigt xx, yy, engineering xy)."""
    U1, U2, U3, U4, U5 = lamina_invariants(E1, E2, G12, nu12)
    D0 = np.array([[U1, U4, 0.0], [U4, U1, 0.0], [0.0, 0.0, U5]])
    D1 = np.array([[U2, 0.0, 0.0], [0.0, -U2, 0.0], [0.0, 0.0, 0.0]])
    D2 = np.array([[0.0, 0.0, U2 / 2], [0.0, 0.0, U2 / 2], [U2 / 2, U2 / 2, 0.0]])
    D3 = np.array([[U3, -U3, 0.0], [-U3, U3, 0.0], [0.0, 0.0, -U3]])
    D4 = np.array([[0.0, 0.0, U3], [0.0, 0.0, -U3], [U3, -U3, 0.0]])
    return D0, D1, D2, D3, D4


def element_matrix(D, dx=1.0, dy=1.0):
    """∫ Bᵀ D B over a dx × dy Q4 element (2 × 2 Gauss), nodes counter-clockwise from bottom-left."""
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    gauss = (-1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0))
    KE = np.zeros((8, 8))
    for xi in gauss:
        for eta in gauss:
            dN_dx = np.array([cx * (1 + cy * eta) / 4 for cx, cy in corners]) * (2.0 / dx)
            dN_dy = np.array([cy * (1 + cx * xi) / 4 for cx, cy in corners]) * (2.0 / dy)
            B = np.zeros((3, 8))
            B[0, 0::2], B[1, 1::2], B[2, 0::2], B[2, 1::2] = dN_dx, dN_dy, dN_dy, dN_dx
            KE += B.T @ D @ B * (dx / 2.0) * (dy / 2.0)
    return KE


class Q4Orthotropic(Q4PlaneStress):
    """Plane stress with a fibre angle per element (orthotropic lamina), Q4 elements."""

    name = "q4_orthotropic"
    label = "2-D Q4 fibre-reinforced (orthotropic, angle per element)"
    order = 18
    provides = (ELASTIC_ENERGY,)
    fields = ("angle",)
    params = (
        Param("E2_ratio", 0.1, "Transverse stiffness", "E2 / E1: stiffness across the fibres relative to along.",
              min=1e-3, max=1.0, step=0.05, decimals=4),
        Param("G12_ratio", 0.05, "Shear stiffness", "G12 / E1.", min=1e-4, max=1.0, step=0.01, decimals=4),
        Param("nu12", 0.3, "Poisson's ratio ν12", "Major Poisson's ratio of the lamina.", min=0.0, max=0.49,
              step=0.05, decimals=3),
    )

    def initialize(self, problem, settings, interpolation=None):
        super().initialize(problem, settings, interpolation)
        parts = constitutive_parts(1.0, settings.get("E2_ratio", 0.1), settings.get("G12_ratio", 0.05),
                                   settings.get("nu12", 0.3))
        self.K_parts = np.array([element_matrix(D, problem.dx, problem.dy) for D in parts])     # (5, 8, 8)
        self.field_values = {"angle": np.zeros(self.shape)}

    def _angles(self):
        return self._per_element(np.asarray(self.field_values["angle"], dtype=float).reshape(self.shape))

    def _element_matrices(self, theta):
        c2, s2, c4, s4 = np.cos(2 * theta), np.sin(2 * theta), np.cos(4 * theta), np.sin(4 * theta)
        K0, K1, K2, K3, K4 = self.K_parts
        return (K0[None] + c2[:, None, None] * K1 + s2[:, None, None] * K2 + c4[:, None, None] * K3
                + s4[:, None, None] * K4)

    def _element_derivatives(self, theta):
        c2, s2, c4, s4 = np.cos(2 * theta), np.sin(2 * theta), np.cos(4 * theta), np.sin(4 * theta)
        _, K1, K2, K3, K4 = self.K_parts
        return (-2 * s2[:, None, None] * K1 + 2 * c2[:, None, None] * K2 - 4 * s4[:, None, None] * K3
                + 4 * c4[:, None, None] * K4)

    def solve(self, density):
        from scipy.sparse import coo_matrix
        from scipy.sparse.linalg import spsolve
        problem, scenario = self.problem, self.problem.scenario
        layout, edof = dof_layout(problem), element_dofs(problem)
        stiffness = self.material.stiffness(density.reshape(-1, order="F"), scenario.E0, scenario.Emin)
        KE = self._element_matrices(self._angles())                                   # (n, 8, 8)
        values = (KE.transpose(0, 2, 1).reshape(len(KE), 64) * stiffness[:, None]).ravel()
        rows, cols = np.tile(edof, (1, 8)).ravel(), np.repeat(edof, 8, axis=1).ravel()
        K = coo_matrix((values, (rows, cols)), shape=(layout.ndof, layout.ndof)).tocsc()
        K = (K + K.T) * 0.5
        Kff = K[layout.free_dofs][:, layout.free_dofs]
        U = np.zeros((layout.ndof, len(layout.forces)))
        energies, compliances = [], []
        for k, (_, f) in enumerate(layout.forces):
            U[layout.free_dofs, k] = spsolve(Kff, f[layout.free_dofs])
            ue = U[edof, k]
            energy = np.einsum("ei,eij,ej->e", ue, KE, ue)
            energies.append(self._field(energy))
            compliances.append(float(np.sum(stiffness * energy)))
        state = Q4Solution(density, stiffness, U, Kff, [w for w, _ in layout.forces], energies, compliances)
        state.KE = KE
        return state

    def mutual_energy(self, state, case, adjoint):
        ue, ve = state.U[self.edof, case], adjoint[self.edof]
        return self._field(np.einsum("ei,eij,ej->e", ve, state.KE, ue))

    def field_energy(self, state, case, name):
        if name != "angle":
            return super().field_energy(state, case, name)
        ue = state.U[self.edof, case]
        dK = self._element_derivatives(self._angles())
        return self._field(state.stiffness * np.einsum("ei,eij,ej->e", ue, dK, ue))
