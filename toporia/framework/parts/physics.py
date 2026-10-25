# framework/parts/physics.py — the interface a physics engine implements.
#
# A physics engine turns a physical density field into a solved state, and
# answers a fixed set of questions about that state.  Responses
# (plugins/responses) are written against these questions only, so one
# compliance or stress response works on every engine that can answer them:
#
#     density ──Physics.solve──> state ──Response.evaluate──> value, gradient
#                                  ▲                              │
#                                  └──── adjoint solves, element ─┘
#                                        quantities on request
#
# Which questions an engine can answer is declared in `provides`, as feature
# names.  A response lists the features it `requires`; a model can offer a
# response exactly when its engine provides everything that response needs.
#
# Every field going in or out has the shape of the density, (nely, nelx), with
# an optional trailing axis (e.g. 3 stress components).  Displacements and
# adjoint vectors are opaque: a response receives them from one engine method
# and hands them to another, and never indexes them, so it never depends on a
# degree-of-freedom numbering.
#
# This module contains no mathematics and imports nothing from toporia.plugins.

from abc import ABC, abstractmethod

#: Feature: the weighted compliance and the element strain energies behind it.
ELASTIC_ENERGY = "elastic_energy"
#: Feature: element stresses, adjoint solves and the mutual energies they need.
STRESS = "stress"
#: Feature: steady heat conduction: the thermal compliance and the element energies behind it.
THERMAL_ENERGY = "thermal_energy"

# ── NONLINEAR (feature name; its methods are in the section at the end of Physics) ──
#: Feature: the end compliance fᵀu of a non-linear solve and its adjoint sensitivity
#: (geometric non-linearity: R(u, ρ) = f_int(u, ρ) − f = 0 at the final load).
END_COMPLIANCE = "end_compliance"


class Physics(ABC):
    """A physics engine: solves the state for a density, answers questions about it.

    Class attributes describe the engine, as for every other plugin:

        name, label, order   registry key, menu text, menu position
        params               tunable parameters (framework.params.Param)
        provides             the feature names (ELASTIC_ENERGY, STRESS, ...) it answers
        uses_interpolation   True when material stiffness comes from a material law
                             (framework/parts/interpolation.py) chosen in the solver

    Only `initialize` and `solve` are required.  The other methods belong to a
    feature; implement the ones of every feature listed in `provides`.
    """

    name = ""
    label = ""
    order = 100
    params = ()
    provides = ()
    uses_interpolation = False
    #: The problem dimensions the engine solves: (2,) plane, (3,) solid.
    dims = (2,)

    @abstractmethod
    def initialize(self, problem, settings, interpolation=None):
        """Prepare for a run.

        `settings` holds this engine's own Param values.  `interpolation` is the
        material law (framework.parts.interpolation.Interpolation) for an engine
        that declares uses_interpolation; None means the engine's default.
        """

    @abstractmethod
    def solve(self, density):
        """Solve the state for a physical density field; return an opaque state object.

        The state must carry `density` (the field it was solved for) and
        `weights` (one per load case, in scenario order).
        """

    # ── Material interpolation (needed by both features below) ────────────────

    def stiffness_slope(self, state):
        """d(stiffness)/d(density) per element: how the material scales with density."""
        raise NotImplementedError(f"{type(self).__name__} does not provide stiffness_slope")

    # ── ELASTIC_ENERGY ────────────────────────────────────────────────────────

    def compliance(self, state, case):
        """fᵀu of one load case."""
        raise NotImplementedError(f"{type(self).__name__} does not provide {ELASTIC_ENERGY!r}")

    def strain_energy(self, state, case):
        """u_eᵀ K_e u_e per element for one load case, with K_e at unit stiffness.

        Multiplied by stiffness_slope this is minus the compliance sensitivity.
        """
        raise NotImplementedError(f"{type(self).__name__} does not provide {ELASTIC_ENERGY!r}")

    # ── STRESS ────────────────────────────────────────────────────────────────

    def element_stress(self, state, case):
        """Stress of every element for one load case, of solid material, shape (..., n_components).

        For 2-D plane stress the components are Voigt (σxx, σyy, τxy).
        """
        raise NotImplementedError(f"{type(self).__name__} does not provide {STRESS!r}")

    def stress_load(self, state, case, stress_sensitivity):
        """Turn ∂g/∂σ per element into ∂g/∂u: the right-hand side of an adjoint solve."""
        raise NotImplementedError(f"{type(self).__name__} does not provide {STRESS!r}")

    def adjoint(self, state, load):
        """Solve K λ = load for the current state, with the same supports as the state."""
        raise NotImplementedError(f"{type(self).__name__} does not provide {STRESS!r}")

    def mutual_energy(self, state, case, adjoint):
        """λ_eᵀ K_e u_e per element, with K_e at unit stiffness.

        A response g(u(ρ)) has the sensitivity −stiffness_slope · mutual_energy
        through the displacements.
        """
        raise NotImplementedError(f"{type(self).__name__} does not provide {STRESS!r}")

    # ── THERMAL_ENERGY ────────────────────────────────────────────────────────
    #
    # Steady heat conduction: a scalar temperature per node, a conductivity
    # that follows the density (stiffness_slope above is then
    # d(conductivity)/d(density)), supports as fixed temperature and loads as
    # heat input.

    def thermal_compliance(self, state, case):
        """qᵀT of one load case: the heat input weighted by the temperature it produces."""
        raise NotImplementedError(f"{type(self).__name__} does not provide {THERMAL_ENERGY!r}")

    def thermal_energy(self, state, case):
        """T_eᵀ K_e T_e per element for one load case, with K_e at unit conductivity.

        Multiplied by stiffness_slope this is minus the thermal-compliance sensitivity.
        """
        raise NotImplementedError(f"{type(self).__name__} does not provide {THERMAL_ENERGY!r}")

    # ── NONLINEAR ─────────────────────────────────────────────────────────────
    #
    # END_COMPLIANCE.  The equilibrium is non-linear in the displacements, so the
    # compliance is no longer minus a sum of element energies and the sensitivity
    # needs an adjoint solve with the tangent stiffness K_T(u), which is symmetric:
    #
    #     C = fᵀu,   K_T λ = f,   dC/dρ_e = −λ_eᵀ ∂R_e/∂ρ_e

    def end_compliance(self, state, case):
        """fᵀu of one load case, at the final load of a non-linear solve."""
        raise NotImplementedError(f"{type(self).__name__} does not provide {END_COMPLIANCE!r}")

    def end_compliance_sensitivity(self, state, case):
        """dC/dρ per element of the end compliance of one load case, shaped like the density.

        Exact, by the adjoint equation K_T(u) λ = f; the engine owns the equilibrium
        residual R, so it supplies ∂R_e/∂ρ_e.
        """
        raise NotImplementedError(f"{type(self).__name__} does not provide {END_COMPLIANCE!r}")


# ── MODES ─────────────────────────────────────────────────────────────────────
#
# Free vibration: the generalised eigenproblem  K φ = λ M φ,  λ = ω².  Modes are
# mass-normalised (φᵀ M φ = 1).  Provided by plugins/physics/q4_dynamic.py.

#: Feature: the lowest eigenvalues of the structure and their sensitivities.
MODES = "modes"


class ModalPhysics:
    """The questions a physics engine answers when it provides MODES.

    A mixin-style description: engines implement these two methods; the base class
    Physics stays free of them so engines without vibration need nothing.
    """

    def eigenvalues(self, state, n):
        """The n lowest eigenvalues λ = ω² of K φ = λ M φ, ascending, as a 1-D array."""
        raise NotImplementedError(f"{type(self).__name__} does not provide {MODES!r}")

    def eigenvalue_sensitivity(self, state, i):
        """dλ_i/dρ per element (shape of the density) of the i-th lowest eigenvalue.

        Valid for a simple (non-repeated) eigenvalue; call eigenvalues(state, n)
        with n > i first.
        """
        raise NotImplementedError(f"{type(self).__name__} does not provide {MODES!r}")


# ── HARMONIC ──────────────────────────────────────────────────────────────────
#
# Forced vibration at one driving frequency: (K − ω² M) u = f.  Provided by
# plugins/physics/q4_dynamic.py.

#: Feature: the dynamic compliance fᵀu at a driving frequency, and its adjoint sensitivity.
HARMONIC = "harmonic"


class HarmonicPhysics:
    """The questions a physics engine answers when it provides HARMONIC."""

    def dynamic_compliance(self, state, case, omega):
        """fᵀu of one load case, with (K − ω² M) u = f.  Signed: it changes sign past a resonance."""
        raise NotImplementedError(f"{type(self).__name__} does not provide {HARMONIC!r}")

    def dynamic_compliance_sensitivity(self, state, case, omega):
        """d(fᵀu)/dρ per element (shape of the density): −uᵀ (dK/dρ − ω² dM/dρ) u."""
        raise NotImplementedError(f"{type(self).__name__} does not provide {HARMONIC!r}")
