# plugins/responses/local_stress.py — one stress limit per element, as an augmented-Lagrangian penalty.
#
# Instead of aggregating the stresses into one number (a p-norm, stress.py),
# every element gets its own constraint and its own multiplier.  With the
# relaxed constraint
#
#     g_e = ρ_e^q · σvm_e / σ_lim − 1 − ε (1 − ρ_e)  ≤  0
#
# (ρ^q is the qp-relaxation that lets void elements carry no stress; the ε term
# is a small slack that grows as the element empties — together they are the
# "vanishing constraint" relaxation of the papers, in a simple polynomial form),
# the augmented-Lagrangian penalty of the whole set is
#
#     P = 1/N Σ_e [ λ_e h_e + μ/2 h_e² ],     h_e = max(g_e, −λ_e/μ)
#
# and the optimiser (updaters/augmented_lagrangian.py) minimises  f + P  for a
# few iterations, then moves the multipliers  λ_e ← λ_e + μ h_e  and raises μ.
# That update is exposed here as `update_multipliers`; the response owns λ and
# μ so that nothing else in the framework has to know about them.
#
# Because h_e ≥ −λ_e/μ, the term λ + μ h is never negative, so λ stays ≥ 0, and
# the penalty's slope in g_e is exactly w_e = (λ_e + μ h_e)/N (zero for an
# inactive constraint).  The gradient therefore needs ONE adjoint solve per load
# case, for the weighted sum of all element stress sensitivities — the same
# machinery stress.py uses (physics.stress_load / adjoint / mutual_energy).
#
# The value this response returns is P, NOT a "≤ 0 is satisfied" number: it is
# meant for the augmented_lagrangian updater, which adds it to the objective.
# `exact` is the honest verdict: the largest relaxed stress over the limit, minus
# one, so a run reports whether every element meets its limit.
#
# Stresses use the true element size, like stress.py, so a limit means the same
# at every mesh resolution.  All load cases are constrained (a multiplier per
# case and element).

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.physics import STRESS
from toporia.framework.parts.response import CONSTRAINT_ROLE, Response, ResponseValue
from toporia.plugins.responses.stress import _EPSILON, VON_MISES_2D


class LocalStress(Response):
    """A von Mises limit on every element, enforced by an augmented-Lagrangian penalty."""
    name = "local_stress"
    #: A penalty, not a "<= 0 is satisfied" constraint: only the augmented Lagrangian reads it right.
    only_with_updaters = ("augmented_lagrangian",)
    label = "Local von Mises stress (augmented Lagrangian)"
    use_when = (
        "When every element must stay below a stress limit, not just an aggregate: pairs with the "
        "augmented-Lagrangian updater, typically minimising volume."
    )
    reference = (
        'O. Giraldo-Londono, G. H. Paulino, "PolyStress: a Matlab implementation for local'
        ' stress-constrained topology optimization using the augmented Lagrangian method",'
        ' Struct. Multidisc. Optim. 63 (2021) 2065-2097; G. Senhora, O. Giraldo-Londono, I. Menezes,'
        ' G. H. Paulino, "Topology optimization with local stress constraints: a stress aggregation-free'
        ' approach", Struct. Multidisc. Optim. 62 (2020) 1639-1668. Papers:'
        ' https://doi.org/10.1007/s00158-020-02760-8 https://doi.org/10.1007/s00158-020-02573-9'
    )
    order = 35
    roles = (CONSTRAINT_ROLE,)
    params = (
        Param("limit", 10.0, "Stress limit",
              "Largest allowed von Mises stress in every element, in the scenario's units.",
              min=1e-6, max=1e9, step=1.0, decimals=4),
        Param("q", 0.5, "Relaxation q",
              "Element stress is scaled by density^q, so void elements cannot be over-stressed. "
              "Keep it below the SIMP penalty.",
              min=0.0, max=3.0, step=0.1, decimals=2),
        Param("epsilon", 0.0, "Relaxation ε",
              "Slack ε(1 - density) added to each element's limit: it vanishes for solid elements "
              "and makes an emptying element's constraint inactive. 0 switches it off.",
              min=0.0, max=1.0, step=0.05, decimals=3),
        Param("penalty", 1.0, "Penalty μ (start)",
              "Starting weight of the squared violation. The updater multiplies it every "
              "multiplier update, up to the maximum below.",
              min=1e-6, max=1e9, step=1.0, decimals=3),
        Param("penalty_max", 100.0, "Penalty μ (maximum)",
              "The penalty never grows beyond this.",
              min=1e-6, max=1e12, step=10.0, decimals=3),
    )

    requires = (STRESS,)
    #: The value is a penalty, not a normalised constraint.  A limit far below the stresses makes
    #: every constraint active, so the check is not trivially zero; the multipliers stay fixed.
    gradient_check_settings = {"limit": 1e-3, "epsilon": 0.1}

    def setup(self, physics, problem, settings):
        super().setup(physics, problem, settings)
        self.mu = float(settings["penalty"])
        self.multipliers = None        # λ per load case and element; created at the first evaluation
        self._violation = None         # h at the last evaluated design

    def evaluate(self, state, gradient=True):
        physics, settings = self.physics, self.settings
        vm = getattr(physics, "von_mises_matrix", VON_MISES_2D)
        q, limit, eps = settings["q"], settings["limit"], settings["epsilon"]
        density = state.density
        relaxation = density ** q
        n_cases = len(state.weights)
        if self.multipliers is None:
            self.multipliers = np.zeros((n_cases, *density.shape))
        n_constraints = n_cases * density.size

        cases, g = [], []
        for case in range(n_cases):
            stress = physics.element_stress(state, case)
            von_mises = np.sqrt(np.einsum("...i,ij,...j->...", stress, vm, stress) + _EPSILON)
            cases.append((stress, von_mises))
            g.append(relaxation * von_mises / limit - 1.0 - eps * (1.0 - density))
        g = np.array(g)

        lam, mu = self.multipliers, self.mu
        h = np.maximum(g, -lam / mu)
        value = float(np.sum(lam * h + 0.5 * mu * h * h) / n_constraints)
        peak = float(max(np.max(relaxation * vm_) for _, vm_ in cases))
        # The exact verdict ignores the ε slack: a stricter, honest "stress / limit − 1".
        exact = peak / limit - 1.0
        reported = {"max_stress": peak, "violated_elements": int(np.count_nonzero(g > 0.0)),
                    "stress_ratio": peak / limit}
        self._violation = h
        if not gradient:
            return ResponseValue(value, None, exact, reported)

        weight = (lam + mu * h) / n_constraints          # dP/dg_e
        d_relaxation = np.zeros_like(density, dtype=float)
        solid = density > 0
        d_relaxation[solid] = q * density[solid] ** (q - 1.0)
        slope = physics.stiffness_slope(state)

        sensitivity = np.zeros_like(density, dtype=float)
        for case, (stress, von_mises) in enumerate(cases):
            w = weight[case]
            sensitivity += w * (d_relaxation * von_mises / limit + eps)
            d_stress = (w * relaxation / (limit * von_mises))[..., None] * (stress @ vm)
            adjoint = physics.adjoint(state, physics.stress_load(state, case, d_stress))
            sensitivity -= slope * physics.mutual_energy(state, case, adjoint)
        return ResponseValue(value, sensitivity, exact, reported)

    def update_multipliers(self, growth=1.0):
        """The outer step: λ ← λ + μ h at the last evaluated design, then μ ← min(growth·μ, μ_max)."""
        if self._violation is None:
            raise RuntimeError("update_multipliers needs an evaluation first")
        self.multipliers = self.multipliers + self.mu * self._violation
        self.mu = min(self.mu * growth, self.settings["penalty_max"])
