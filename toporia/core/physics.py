# core/physics.py — the interface a physics engine implements.
#
# A physics engine turns a physical density field into a solved state, and
# answers a fixed set of questions about that state.  Responses
# (library/responses) are written against these questions only, so one
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
# This module contains no mathematics and imports nothing from toporia.library.

from abc import ABC, abstractmethod

#: Feature: the weighted compliance and the element strain energies behind it.
ELASTIC_ENERGY = "elastic_energy"
#: Feature: element stresses, adjoint solves and the mutual energies they need.
STRESS = "stress"


class Physics(ABC):
    """A physics engine: solves the state for a density, answers questions about it.

    Class attributes describe the engine, as for every other plugin:

        name, label, order   registry key, menu text, menu position
        params               tunable parameters (core.params.Param), e.g. a SIMP penalty
        provides             the feature names (ELASTIC_ENERGY, STRESS, ...) it answers

    Only `initialize` and `solve` are required.  The other methods belong to a
    feature; implement the ones of every feature listed in `provides`.
    """

    name = ""
    label = ""
    order = 100
    params = ()
    provides = ()

    @abstractmethod
    def initialize(self, problem, settings):
        """Prepare for a run.  `settings` holds this engine's own Param values."""

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
