# plugins/physics/q4_nonlinear.py — 2-D Q4 geometrically non-linear elasticity (large displacement).
#
# What it is.  The same bilinear Q4 plane-stress element as q4_plane_stress.py, but the
# equilibrium is written on the DEFORMED shape: large displacements and rotations,
# small strains.  Total Lagrangian formulation, Green–Lagrange strain and a
# St Venant–Kirchhoff material (the linear plane-stress law applied to the Green strain):
#
#     F = I + ∇u                       deformation gradient
#     E = ½ (FᵀF − I)                  Green–Lagrange strain   (Voigt: E11, E22, 2·E12)
#     S = D E,   ψ = ½ Eᵀ D E          second Piola–Kirchhoff stress, strain energy density
#     f_int = ∫ B_NLᵀ S dV             internal force,  B_NL = ∂E/∂u  (depends on u)
#     K_T = ∫ B_NLᵀ D B_NL + (geometric stress term) dV     tangent stiffness
#
# Integration is 2×2 Gauss.  A load is applied in `steps` equal increments and each
# increment is solved by Newton–Raphson, R(u) = f_int(u) − λ f = 0, K_T du = −R, with a
# backtracking line search.  If an increment does not converge in `max_newton` iterations
# the solve stops with an error that says where.
#
# Low density — the remedy.  A void element carries almost no stiffness, so under a large
# displacement of its neighbours it is squashed or inverted; its tangent loses meaning and
# Newton stalls (Buhl, Pedersen & Sigmund 2000).  Following the
# idea of Wang, Lazarov, Sigmund & Jensen (2014), the STRAIN ENERGY is interpolated, not
# the stiffness alone:  the element energy is
#
#     W_e(u, ρ) = E(ρ) · [ (1 − s(ρ)) ψ_nonlinear(u) + s(ρ) ψ_linear(u) ]
#
# with E(ρ) the material law (SIMP by default) and s(ρ) a smooth step: 0 above `linear_above`
# (full large-displacement behaviour), 1 below `linear_below` (small-strain behaviour, a
# constant matrix that cannot distort), a smoothstep in between.  Void is therefore a
# harmless linear spring while material is fully non-linear.  This is a re-derivation of the
# principle from the paper (energy interpolation between a non-linear and a linear law),
# not its exact switching function.  The simpler remedy of Buhl et al. (relaxing the
# convergence test in void elements) is not used.
#
# Sensitivity of the end compliance C = fᵀu(ρ) at the final load: the residual is
# R(u, ρ) = f_int(u, ρ) − f, so du/dρ = −K_T⁻¹ ∂R/∂ρ and
#
#     dC/dρ_e = −λ_eᵀ ∂R_e/∂ρ_e,     K_T λ = f        (adjoint; K_T is symmetric but
#                                                       the sensitivity is not minus an energy)
#     ∂R_e/∂ρ_e = E'(ρ) g_e + E(ρ) s'(ρ) (g_lin,e − g_nl,e),   g = unit-stiffness element force.
#
# Open references: Han et al., "An efficient 137-line MATLAB code for
# geometrically nonlinear topology optimization using bi-directional evolutionary structural
# optimization method", Struct. Multidisc. Optim. 63 (2021) (https://doi.org/10.1007/s00158-020-02816-9).  pyMOTO has no geometrically non-linear
# module, so there is no pyMOTO version of this engine.

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

from toporia.framework.params import Param
from toporia.framework.parts.physics import END_COMPLIANCE, Physics
from toporia.plugins.interpolations.simp import SIMP

from .q4_plane_stress import dof_layout, element_dofs, element_stiffness

#: How often a load increment may be halved before the solve gives up (down to 1/2^6 of a load step).
_MAX_CUTS = 6
_GAUSS = (-1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0))
_CORNERS = ((-1, -1), (1, -1), (1, 1), (-1, 1))      # counter-clockwise from bottom-left


class NonlinearConvergenceError(RuntimeError):
    """Newton–Raphson did not converge: the load step is too large or the design too soft."""


def _plane_stress_D(nu):
    """The plane-stress constitutive matrix at unit Young's modulus, Voigt order (11, 22, 2·12)."""
    return np.array([[1.0, nu, 0.0], [nu, 1.0, 0.0], [0.0, 0.0, (1.0 - nu) / 2.0]]) / (1.0 - nu ** 2)


def _gauss_gradients(dx, dy):
    """For each Gauss point: (dN/dx, dN/dy), each of length 4, and the weight dx·dy/4."""
    points = []
    for xi in _GAUSS:
        for eta in _GAUSS:
            dN_dxi = np.array([cx * (1 + cy * eta) / 4 for cx, cy in _CORNERS])
            dN_deta = np.array([cy * (1 + cx * xi) / 4 for cx, cy in _CORNERS])
            points.append((dN_dxi * 2.0 / dx, dN_deta * 2.0 / dy))
    return points, dx * dy / 4.0


def smooth_step(rho, low, high):
    """s(ρ): 1 at or below `low`, 0 at or above `high`, a cubic smoothstep between; and its slope."""
    t = np.clip((rho - low) / (high - low), 0.0, 1.0)
    s = 1.0 - t * t * (3.0 - 2.0 * t)
    slope = np.where((rho > low) & (rho < high), -6.0 * t * (1.0 - t) / (high - low), 0.0)
    return s, slope


class NonlinearElement:
    """Unit-stiffness force and tangent of all elements at once, from their displacements.

    Everything is for E = 1; the caller scales by the element's stiffness and by the
    linear/non-linear mix.  Arrays are (n_elements, 8) for forces and (n, 8, 8) for tangents.
    """

    def __init__(self, nu, dx, dy):
        self.D = _plane_stress_D(nu)
        self.points, self.weight = _gauss_gradients(dx, dy)
        self.KE = element_stiffness(nu, dx, dy)      # the linear element, same integration

    def force_and_tangent(self, Ue, tangent=True):
        """(g_nl, K_nl) of the St Venant–Kirchhoff element at displacements Ue, shape (n, 8)."""
        n = Ue.shape[0]
        ux, uy = Ue[:, 0::2], Ue[:, 1::2]
        g = np.zeros((n, 8))
        K = np.zeros((n, 8, 8)) if tangent else None
        for dNdx, dNdy in self.points:
            H11, H12, H21, H22 = ux @ dNdx, ux @ dNdy, uy @ dNdx, uy @ dNdy       # displacement gradient
            F11, F12, F21, F22 = 1.0 + H11, H12, H21, 1.0 + H22
            # Written with H, not as ½(FᵀF − I): for a small load the latter subtracts two
            # numbers near 1 and loses all the digits the strain has.
            strain = np.stack([H11 + 0.5 * (H11 ** 2 + H21 ** 2), H22 + 0.5 * (H12 ** 2 + H22 ** 2),
                               H12 + H21 + H11 * H12 + H21 * H22], axis=1)
            stress = strain @ self.D.T
            # B_NL = dE/du, one row per strain component, columns (ux1, uy1, ux2, uy2, ...).
            B = np.zeros((n, 3, 8))
            B[:, 0, 0::2] = F11[:, None] * dNdx
            B[:, 0, 1::2] = F21[:, None] * dNdx
            B[:, 1, 0::2] = F12[:, None] * dNdy
            B[:, 1, 1::2] = F22[:, None] * dNdy
            B[:, 2, 0::2] = F11[:, None] * dNdy + F12[:, None] * dNdx
            B[:, 2, 1::2] = F21[:, None] * dNdy + F22[:, None] * dNdx
            g += np.einsum("nij,ni->nj", B, stress) * self.weight
            if tangent:
                material = np.einsum("nki,kl,nlj->nij", B, self.D, B)
                # Geometric (initial-stress) part: S : ∂²E/∂u∂u, the same for x and for y.
                G = (stress[:, 0, None, None] * np.outer(dNdx, dNdx) + stress[:, 1, None, None] * np.outer(dNdy, dNdy)
                     + stress[:, 2, None, None] * (np.outer(dNdx, dNdy) + np.outer(dNdy, dNdx)))
                geometric = np.zeros((n, 8, 8))
                geometric[:, 0::2, 0::2] = G
                geometric[:, 1::2, 1::2] = G
                K += (material + geometric) * self.weight
        return g, K


class NonlinearSolution:
    """Everything one solve produces: the state Q4Nonlinear hands to responses.

    density, weights : as every state
    stiffness        : E(ρ) per element, column-major
    U                : (ndof, n_load_cases) displacements at the final load
    lu               : per load case, the factorised tangent K_T(u) on the free DOFs (for the adjoint)
    end_compliances  : per load case, fᵀu at the final load
    increments       : per load case, the number of Newton iterations of each load step
    """

    def __init__(self, density, stiffness, U, lu, weights, end_compliances, increments):
        self.density = density
        self.stiffness = stiffness
        self.U = U
        self.lu = lu
        self.weights = weights
        self.end_compliances = end_compliances
        self.increments = increments


class Q4Nonlinear(Physics):
    """Large-displacement elasticity on Q4 elements: Newton–Raphson with load steps, energy-interpolated void."""

    name = "q4_nonlinear"
    label = "2-D Q4 large deformation (Toporia)"
    reference = (
        'Total Lagrangian large-displacement elasticity with the void treated by an energy interpolation:'
        ' Q. Wang, B. S. Lazarov, O. Sigmund, J. S. Jensen, CMAME 276 (2014) 453-472; stiffness design'
        ' after T. Buhl, C. B. W. Pedersen, O. Sigmund, Struct. Multidisc. Optim. 19 (2000) 93-104.'
        ' Papers: https://doi.org/10.1016/j.cma.2014.03.021 https://doi.org/10.1007/s001580050089'
    )
    order = 11
    provides = (END_COMPLIANCE,)
    uses_interpolation = True
    #: The conformance check scales the benchmark's loads by this: they are made for a linear
    #: model and would push the soft random check design far outside what Newton can follow.
    check_load_scale = 0.02
    params = (
        Param("steps", 5, "Load steps", "The load is applied in this many equal increments; more are safer for large loads.",
              min=1, max=1000, source="Incremental Newton–Raphson, as in Buhl, Pedersen & Sigmund (2000)."),
        Param("newton_tol", 1e-10, "Newton tolerance",
              "A step has converged when the residual force is below this fraction of the full load.",
              min=1e-14, max=1e-2, step=1e-8, decimals=12),
        Param("max_newton", 30, "Newton iterations", "Most Newton iterations per load step before the solve is abandoned.",
              min=1, max=500),
        Param("linear_below", 0.1, "Linear below density",
              "Elements at or below this physical density use the linear small-strain law, which cannot distort.",
              min=0.0, max=0.9, step=0.05, decimals=2,
              source="Energy interpolation after Wang, Lazarov, Sigmund & Jensen, CMAME 276 (2014) 453-472."),
        Param("linear_above", 0.2, "Non-linear above density",
              "Elements at or above this physical density are fully non-linear; in between the two laws are blended smoothly.",
              min=0.01, max=1.0, step=0.05, decimals=2,
              source="Energy interpolation after Wang, Lazarov, Sigmund & Jensen, CMAME 276 (2014) 453-472."),
    )

    def initialize(self, problem, settings, interpolation=None):
        scenario = problem.scenario
        self.problem = problem
        self.settings = dict(settings)
        if self.settings["linear_above"] <= self.settings["linear_below"]:
            raise ValueError("linear_above must exceed linear_below so the two laws can be blended")
        self.material = interpolation if interpolation is not None else SIMP()
        self.layout = dof_layout(problem)
        self.edof = element_dofs(problem)
        self.element = NonlinearElement(scenario.nu, problem.dx, problem.dy)
        self.shape = (problem.nely, problem.nelx)
        ndof = self.layout.ndof
        self.iK = np.tile(self.edof, (1, 8)).ravel()
        self.jK = np.repeat(self.edof, 8, axis=1).ravel()
        self.ndof = ndof

    # ── The element laws, mixed by density ────────────────────────────────────

    def _mix(self, density):
        """E(ρ), E'(ρ), s(ρ), s'(ρ) per element, column-major."""
        scenario = self.problem.scenario
        x = density.reshape(-1, order="F")
        E = self.material.stiffness(x, scenario.E0, scenario.Emin)
        dE = self.material.slope(density, scenario.E0, scenario.Emin).reshape(-1, order="F")
        s, ds = smooth_step(x, self.settings["linear_below"], self.settings["linear_above"])
        return E, dE, s, ds

    def _forces(self, U, E, s, tangent):
        """Internal force vector over all DOFs and, if asked, the assembled tangent (free block data)."""
        Ue = U[self.edof]
        g_nl, K_nl = self.element.force_and_tangent(Ue, tangent)
        g_lin = Ue @ self.element.KE
        f_el = E[:, None] * ((1.0 - s)[:, None] * g_nl + s[:, None] * g_lin)
        f = np.bincount(self.edof.ravel(), weights=f_el.ravel(), minlength=self.ndof)
        if not tangent:
            return f, None
        K_el = E[:, None, None] * ((1.0 - s)[:, None, None] * K_nl + s[:, None, None] * self.element.KE[None])
        K = coo_matrix((K_el.ravel(), (self.iK, self.jK)), shape=(self.ndof, self.ndof)).tocsc()
        return f, K

    # ── Newton–Raphson with load stepping ─────────────────────────────────────

    def _newton(self, U, load, E, s):
        """Newton–Raphson from U to equilibrium under `load`: (U, K, iterations), or None if it fails."""
        free = self.layout.free_dofs
        tol, max_newton = self.settings["newton_tol"], self.settings["max_newton"]
        reference = float(np.linalg.norm(self._reference)) or 1.0
        f_int, K = self._forces(U, E, s, tangent=True)
        residual = (f_int - load)[free]
        norm = np.linalg.norm(residual)
        used = 0
        while norm > tol * reference:
            if used >= max_newton:
                self._last_residual = norm / reference
                return None
            lu = splu(K[free][:, free].tocsc())
            delta = lu.solve(-residual)
            # Round-off floor: a soft void next to solid makes the residual noisy at about
            # 1e-16 times the stiffness ratio; an update this small cannot improve the state.
            if np.linalg.norm(delta) <= 1e-12 * max(np.linalg.norm(U), 1e-300):
                break
            # Backtrack when the full Newton step increases the residual, as it can
            # for a soft or strongly rotating region.
            alpha = 1.0
            for _ in range(8):
                trial = U.copy()
                trial[free] += alpha * delta
                f_trial, _ = self._forces(trial, E, s, tangent=False)
                if np.linalg.norm((f_trial - load)[free]) < norm or alpha < 1e-3:
                    break
                alpha *= 0.5
            U = trial
            f_int, K = self._forces(U, E, s, tangent=True)
            residual = (f_int - load)[free]
            norm = np.linalg.norm(residual)
            used += 1
        return U, K, used

    def _solve_case(self, f_ext, E, s, case):
        """Displacements and the final factorised tangent for one load vector.

        The load goes up in `steps` increments; an increment Newton cannot follow is halved
        (down to 1/2^_MAX_CUTS of a step) and the smaller size is kept for the rest of the load.
        """
        free = self.layout.free_dofs
        steps = self.settings["steps"]
        self._reference = f_ext[free]
        U = np.zeros(self.ndof)
        iterations = []
        K = None
        fraction, increment = 0.0, 1.0 / steps
        smallest = increment / 2 ** _MAX_CUTS
        while fraction < 1.0 - 1e-12:
            target = min(fraction + increment, 1.0)
            result = self._newton(U, f_ext * target, E, s)
            if result is None:
                increment /= 2.0
                if increment < smallest:
                    raise NonlinearConvergenceError(
                        f"Newton–Raphson did not converge beyond {fraction:.1%} of the load "
                        f"(load case {case + 1}): {self.settings['max_newton']} iterations were not enough even "
                        f"for an increment of {increment * 200:.2g}% of the load (residual "
                        f"{self._last_residual:.2e} of the full load, needed {self.settings['newton_tol']:.0e}). "
                        f"The design probably cannot carry this load without buckling or snapping; "
                        f"use a smaller load.")
                continue
            U, K, used = result
            iterations.append(used)
            fraction = target
            # An increment is never made larger again after a cut: near a limit point, growing it
            # back only to fail again would creep towards the limit without end.
        lu = splu(K[free][:, free].tocsc())       # the tangent at the final, converged state
        return U, lu, iterations

    def solve(self, density):
        E, _, s, _ = self._mix(density)
        U = np.zeros((self.ndof, len(self.layout.forces)))
        lus, compliances, increments = [], [], []
        for case, (_, f_ext) in enumerate(self.layout.forces):
            U[:, case], lu, used = self._solve_case(f_ext, E, s, case)
            lus.append(lu)
            compliances.append(float(f_ext @ U[:, case]))
            increments.append(used)
        weights = [weight for weight, _ in self.layout.forces]
        return NonlinearSolution(density, E, U, lus, weights, compliances, increments)

    # ── END_COMPLIANCE ────────────────────────────────────────────────────────

    def end_compliance(self, state, case):
        return state.end_compliances[case]

    def end_compliance_sensitivity(self, state, case):
        free = self.layout.free_dofs
        f_ext = self.layout.forces[case][1]
        adjoint = np.zeros(self.ndof)
        adjoint[free] = state.lu[case].solve(f_ext[free])          # K_T λ = f
        _, dE, s, ds = self._mix(state.density)
        E = state.stiffness
        Ue = state.U[self.edof, case]
        g_nl, _ = self.element.force_and_tangent(Ue, tangent=False)
        g_lin = Ue @ self.element.KE
        # ∂R_e/∂ρ_e : the stiffness slope acts on the mixed force, the switch on the difference of laws.
        dR = dE[:, None] * ((1.0 - s)[:, None] * g_nl + s[:, None] * g_lin) + (E * ds)[:, None] * (g_lin - g_nl)
        sensitivity = -np.sum(adjoint[self.edof] * dR, axis=1)
        return sensitivity.reshape(self.shape, order="F")
