# plugins/physics/q4_dynamic.py — 2-D Q4 elasticity with a mass matrix: vibration.
#
# The static Q4 plane-stress engine (q4_plane_stress.py, untouched) plus a mass
# matrix M, so two more questions can be answered about a design:
#
#   MODES      free vibration     K φ = λ M φ          λ = ω²,  φᵀ M φ = 1
#   HARMONIC   forced vibration   (K − ω² M) u = f     dynamic compliance fᵀu
#
# Everything the static engine answers (compliance, stress) still works, so a
# model built on this engine offers all of those responses as well.
#
# Mass.  Element mass is m(ρ) · M_e with the consistent Q4 matrix
#
#     M_e = ρ0 t dx dy / 36 · [4 2 1 2; 2 4 2 1; 1 2 4 2; 2 1 2 4] ⊗ I₂
#
# (or its row-sum lumped version, a diagonal).  With the SIMP stiffness ρ^p and
# a mass that is simply ρ, a void element has stiffness/mass ~ ρ^(p−1) → 0, so
# the lowest "eigenmodes" are spurious oscillations of the void.  Pedersen
# (2000) and Du & Olhoff (2007) cure this by letting the mass fall faster than
# the stiffness below a threshold ρc:
#
#     m(ρ) = ρ                        ρ ≥ ρc
#     m(ρ) = ρc (ρ/ρc)^r              ρ < ρc       (r > p; Du & Olhoff: ρc = 0.1, r = 6)
#
# which is continuous at ρc.  Setting the threshold to 0 gives the plain linear
# mass m = ρ.
#
# Non-structural mass: `attached_mass` is a lumped mass spread evenly over the
# load nodes (the nodes the scenario's point loads and load holes mark), so a
# preset can carry a payload without a separate way of describing one.  It does
# not depend on the design.
#
# Sensitivities (K φ = λ M φ, φ mass-normalised, λ simple):
#
#     dλ/dρ_e = φ_eᵀ (dE/dρ_e K_e − λ dm/dρ_e M_e) φ_e
#     d(fᵀu)/dρ_e = −u_eᵀ (dE/dρ_e K_e − ω² dm/dρ_e M_e) u_e        (A = K − ω² M is symmetric)
#
# The eigenproblem is solved with ARPACK in shift-invert mode around zero
# (scipy.sparse.linalg.eigsh), which finds the lowest eigenvalues quickly.
#
# References: A. Díaz, N. Kikuchi, IJNME 35 (1992) 1487-1502 (eigenvalue
# optimisation); N. L. Pedersen, SMO 20 (2000) 2-11 (the mass fix);
# J. Du, N. Olhoff, SMO 34 (2007) 91-110 (maximum fundamental frequency).

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import eigsh, spsolve

from toporia.framework.params import Param
from toporia.framework.parts.physics import (
    ELASTIC_ENERGY,
    HARMONIC,
    MODES,
    STRESS,
    HarmonicPhysics,
    ModalPhysics,
)

from .q4_plane_stress import Q4PlaneStress, Q4Solution, _solve

#: The mass-related parameters, shared with the pyMOTO model (models/pymoto_dynamic.py).
MASS_DENSITY = Param("mass_density", 1.0, "Mass density",
                     "Density of the solid material, in the scenario's units (with the Young's modulus E0 it "
                     "sets the eigenvalues λ = ω² and the frequencies).",
                     min=1e-9, max=1e9, step=0.1, decimals=4,
                     source="Toporia's own; the material constant of Du & Olhoff (2007).")
LOW_DENSITY_BELOW = Param("low_density_below", 0.1, "Low-density threshold",
                          "Below this density the mass falls faster than the stiffness, which removes the "
                          "spurious vibration modes of void regions. 0 switches the fix off (mass = density).",
                          min=0.0, max=0.5, step=0.05, decimals=3,
                          source="Pedersen, SMO 20 (2000) 2-11; 0.1 is the value of Du & Olhoff, SMO 34 (2007) 91-110.")
LOW_DENSITY_EXPONENT = Param("low_density_exponent", 6.0, "Low-density exponent",
                             "How fast the mass falls below the threshold; it must exceed the stiffness penalty "
                             "for the fix to work.",
                             min=1.0, max=12.0, step=0.5, decimals=1,
                             source="Du & Olhoff, SMO 34 (2007) 91-110, who use 6.")
ATTACHED_MASS = Param("attached_mass", 0.0, "Attached mass",
                      "Non-structural mass in total, spread evenly over the load nodes (the point loads and "
                      "load holes): a payload that the design has to carry.",
                      min=0.0, max=1e9, step=0.5, decimals=4,
                      source="The non-structural centre mass of Du & Olhoff, SMO 34 (2007) 91-110.")


def mass_interpolation(density, threshold, exponent):
    """m(ρ) and dm/dρ: the mass of an element as a fraction of the solid one (Pedersen's fix below `threshold`)."""
    density = np.maximum(density, 0.0)
    if threshold <= 0.0:
        return density, np.ones_like(density)
    low = density < threshold
    ratio = np.where(low, density / threshold, 1.0)
    mass = np.where(low, threshold * ratio ** exponent, density)
    slope = np.where(low, exponent * ratio ** (exponent - 1.0), 1.0)
    return mass, slope


def element_mass(dx, dy, thickness=1.0, lumped=False):
    """The 8×8 mass matrix of one Q4 element of unit density, DOF order as element_stiffness.

    Consistent: ∫ NᵀN dA.  Lumped: its row sums on the diagonal (a quarter of the element
    mass per node and direction), which has no negative-weight entries and is cheaper.
    """
    shape = np.array([[4, 2, 1, 2], [2, 4, 2, 1], [1, 2, 4, 2], [2, 1, 2, 4]], dtype=float) / 36.0
    consistent = np.kron(shape, np.eye(2)) * dx * dy * thickness
    return np.diag(consistent.sum(axis=1)) if lumped else consistent


class DynamicSolution(Q4Solution):
    """A Q4Solution that also carries the mass matrix; the state of Q4Dynamic.

    M          : free-free mass matrix (the mass of the design plus the attached mass)
    mass_slope : dm/dρ per element (column-major), for the sensitivities
    cache      : eigen-decompositions and harmonic solves already made for this design
    """

    def __init__(self, base, M, mass_slope):
        super().__init__(base.density, base.stiffness, base.U, base.Kff, base.weights,
                         base.energies, base.compliances)
        self.M = M
        self.mass_slope = mass_slope
        self.cache = {}


class Q4Dynamic(Q4PlaneStress, ModalPhysics, HarmonicPhysics):
    """Q4PlaneStress plus a mass matrix: eigenfrequencies and harmonic response.

    The mass interpolation, mass type and attached mass are Params; the stiffness
    comes from the solver's material law as in the static engine.
    """

    name = "q4_dynamic"
    label = "2-D Q4 with vibration (Toporia)"
    order = 11
    provides = (ELASTIC_ENERGY, STRESS, MODES, HARMONIC)
    uses_interpolation = True
    params = (
        MASS_DENSITY, LOW_DENSITY_BELOW, LOW_DENSITY_EXPONENT, ATTACHED_MASS,
        Param("mass_type", "consistent", "Mass matrix",
              "Consistent: the exact Q4 mass matrix (more accurate frequencies). Lumped: a diagonal matrix "
              "(cheaper, slightly lower frequencies).",
              choices=(("consistent", "Consistent"), ("lumped", "Lumped")),
              source="Toporia's own; both are standard (Cook et al., Concepts and Applications of FEA)."),
    )

    def initialize(self, problem, settings, interpolation=None):
        super().initialize(problem, settings, interpolation)
        self.mass_density = settings["mass_density"]
        self.threshold = settings["low_density_below"]
        self.exponent = settings["low_density_exponent"]
        self.ME = self.mass_density * element_mass(problem.dx, problem.dy, lumped=settings["mass_type"] == "lumped")
        self.attached = self._attached_mass(settings["attached_mass"])

    def _attached_mass(self, total):
        """The diagonal of the non-structural mass: `total` shared by the load nodes, in x and y."""
        diagonal = np.zeros(self.layout.ndof)
        nodes = np.unique(np.concatenate(
            [self.layout.node_ids[mask] for mask in self.problem.load_node_sets] or [np.array([], dtype=int)]))
        if total > 0.0 and nodes.size:
            diagonal[2 * nodes] = diagonal[2 * nodes + 1] = total / nodes.size
        return diagonal

    def solve(self, density):
        base = _solve(self.problem, density, self.material)
        mass, slope = mass_interpolation(density.reshape(-1, order="F"), self.threshold, self.exponent)
        ndof, free = self.layout.ndof, self.layout.free_dofs
        iM = np.tile(self.edof, (1, 8)).ravel()
        jM = np.repeat(self.edof, 8, axis=1).ravel()
        sM = (self.ME.ravel(order="F")[None, :] * mass[:, None]).ravel()
        M = coo_matrix((sM, (iM, jM)), shape=(ndof, ndof)).tocsc() + diags(self.attached)
        return DynamicSolution(base, M[free][:, free].tocsc(), slope)

    # ── MODES ─────────────────────────────────────────────────────────────────

    def _modes(self, state, n):
        """Mass-normalised eigenpairs, at least n of them, cached on the state."""
        have = state.cache.get("modes")
        if have is not None and have[0].size >= n:
            return have
        size = state.Kff.shape[0]
        k = min(max(n, 1), size - 2)
        # Shift-invert about zero: K is positive definite (void keeps Emin), so K itself is the operator to factor.
        # A fixed start vector (ARPACK's own is random) makes the same design give the same eigenvalues
        # to the last bit, which the value-without-gradient check and reproducible runs rely on.
        start = np.random.default_rng(0).standard_normal(size)
        values, vectors = eigsh(state.Kff, k=k, M=state.M, sigma=0.0, which="LM", v0=start)
        order = np.argsort(values)
        values, vectors = values[order], vectors[:, order]
        vectors = vectors / np.sqrt(np.einsum("ij,ij->j", vectors, state.M @ vectors))
        state.cache["modes"] = (values, vectors)
        return values, vectors

    def eigenvalues(self, state, n):
        return self._modes(state, n)[0][:n]

    def _full(self, free_vector):
        """A vector over the free DOFs spread over all DOFs (zero at the supports)."""
        full = np.zeros(self.layout.ndof)
        full[self.layout.free_dofs] = free_vector
        return full

    def eigenvalue_sensitivity(self, state, i):
        values, vectors = self._modes(state, i + 1)
        phi = self._full(vectors[:, i])[self.edof]
        stiffness_energy = np.sum((phi @ self.KE) * phi, axis=1)
        mass_energy = np.sum((phi @ self.ME) * phi, axis=1)
        scenario = self.problem.scenario
        e_slope = self.material.slope(state.density, scenario.E0, scenario.Emin)
        return e_slope * self._field(stiffness_energy) - values[i] * self._field(state.mass_slope * mass_energy)

    # ── HARMONIC ──────────────────────────────────────────────────────────────

    def _harmonic_displacement(self, state, case, omega):
        """u of (K − ω² M) u = f for one load case, over all DOFs; cached."""
        key = ("harmonic", case, omega)
        if key not in state.cache:
            free = self.layout.free_dofs
            force = self.layout.forces[case][1]
            system = (state.Kff - omega ** 2 * state.M).tocsc()
            state.cache[key] = self._full(spsolve(system, force[free]))
        return state.cache[key]

    def dynamic_compliance(self, state, case, omega):
        force = self.layout.forces[case][1]
        return float(force @ self._harmonic_displacement(state, case, omega))

    def dynamic_compliance_sensitivity(self, state, case, omega):
        u = self._harmonic_displacement(state, case, omega)[self.edof]
        stiffness_energy = np.sum((u @ self.KE) * u, axis=1)
        mass_energy = np.sum((u @ self.ME) * u, axis=1)
        scenario = self.problem.scenario
        e_slope = self.material.slope(state.density, scenario.E0, scenario.Emin)
        return -(e_slope * self._field(stiffness_energy)
                 - omega ** 2 * self._field(state.mass_slope * mass_energy))


__all__ = ["Q4Dynamic", "DynamicSolution", "element_mass", "mass_interpolation"]
