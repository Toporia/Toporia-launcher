# plugins/responses/eigenfrequency.py — the lowest natural frequency of the design.
#
# The fundamental frequency decides how a structure answers a vibrating load, so a
# classic goal is to MAXIMISE the lowest eigenvalue λ1 = ω1² of K φ = λ M φ, or to
# keep it above a limit.
#
# λ1 alone is not differentiable where two eigenvalues meet, and maximising it
# makes them meet: the optimiser raises λ1 until λ2 (often a mirror-image mode) is
# just as low (Du & Olhoff 2007).  So the response uses a smooth minimum of the
# lowest few eigenvalues, a p-norm of their reciprocals:
#
#     λ_agg = ( Σ_i λ_i^(−p) )^(−1/p)  ≤  λ1,     → λ1 as p → ∞
#
#     dλ_agg/dλ_i = (λ_agg / λ_i)^(p+1)
#
# with the eigenvalue sensitivities dλ_i/dρ of the physics (MODES).  With
# `modes` = 1 it is exactly λ1.  The value is the aggregate; the true λ1 is
# recorded as omega_1 = √λ1 (and the others), so the reported frequency is exact.
#
# As an objective the value is −λ_agg / λ_ref, where λ_ref is the aggregate at
# the first design evaluated: a fixed number that only gives the objective the
# size of one, whatever the units of E0 and the mass density.  As a constraint it
# is 1 − λ_agg / limit ≤ 0.  Both signs change along a run, so use an updater
# that accepts that (MMA, not OC).
#
# References: A. Díaz, N. Kikuchi, IJNME 35 (1992) 1487-1502; J. Du, N. Olhoff,
# SMO 34 (2007) 91-110 (multiple eigenvalues).

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.physics import MODES
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response, ResponseValue

MODES_PARAM = Param("modes", 3, "Modes",
                    "How many of the lowest eigenvalues are taken together. 1 is the fundamental alone; "
                    "more lets the optimiser raise a group of near-equal eigenvalues at once.",
                    min=1, max=12, step=1,
                    source="Du & Olhoff, SMO 34 (2007) 91-110, on repeated eigenvalues.")
SHARPNESS_PARAM = Param("p", 16.0, "Aggregation sharpness",
                        "Exponent of the smooth minimum over the modes. Higher is closer to the true lowest "
                        "eigenvalue but less smooth; the aggregate is never above it.",
                        min=1.0, max=200.0, step=2.0, decimals=1,
                        source="Toporia's own; a p-norm of the reciprocals, as used for stress by Le et al. (2010).")


def soft_minimum(values, p):
    """(λ_agg, dλ_agg/dλ_i) of the smooth minimum of positive `values` (ascending, so values[0] is the least)."""
    ratio = (values[0] / values) ** p
    aggregate = values[0] * ratio.sum() ** (-1.0 / p)
    return aggregate, (aggregate / values) ** (p + 1.0)


class _EigenfrequencyBase(Response):
    """What the objective and the constraint share: the aggregate eigenvalue and its gradient."""

    requires = (MODES,)

    def _aggregate(self, state, gradient):
        """(λ_agg, ∂λ_agg/∂ρ or None, the eigenvalues) at a solved state."""
        count, p = int(self.settings["modes"]), self.settings["p"]
        values = self.physics.eigenvalues(state, count)
        aggregate, weights = soft_minimum(values, p)
        if not gradient:
            return aggregate, None, values
        total = np.zeros_like(state.density, dtype=float)
        for i, weight in enumerate(weights):
            total += weight * self.physics.eigenvalue_sensitivity(state, i)
        return aggregate, total, values

    def _reported(self, values):
        return {f"omega_{i + 1}": float(np.sqrt(max(v, 0.0))) for i, v in enumerate(values[:2])}


class Eigenfrequency(_EigenfrequencyBase):
    """Maximise the lowest natural frequency (a smooth minimum of the lowest few eigenvalues)."""

    name = "eigenfrequency"
    label = "Fundamental frequency (maximise)"
    use_when = (
        "When the part must not resonate with low-frequency excitation: pushes the lowest natural "
        "frequency up."
    )
    reference = (
        'Eigenvalue optimisation: A. Diaz, N. Kikuchi, "Solutions to shape and topology eigenvalue'
        ' optimization problems using a homogenization method", Int. J. Numer. Meth. Engng 35 (1992)'
        ' 1487-1502; multiple eigenvalues: J. Du, N. Olhoff, Struct. Multidisc. Optim. 34 (2007) 91-110.'
        ' Papers: https://doi.org/10.1002/nme.1620350707 https://doi.org/10.1007/s00158-007-0101-y'
    )
    order = 40
    roles = (OBJECTIVE_ROLE,)
    params = (MODES_PARAM, SHARPNESS_PARAM)
    advice = ("The lowest frequency is raised until two modes meet, so the sensitivities change sign: use "
              "MMA (q4_dynamic+mma), not OC, and give the design a payload or a support to vibrate against.")

    def setup(self, physics, problem, settings):
        super().setup(physics, problem, settings)
        self._reference = None   # fixed at the first design, so the objective is O(1) in any units

    def evaluate(self, state, gradient=True):
        aggregate, slope, values = self._aggregate(state, gradient)
        if self._reference is None:
            self._reference = aggregate
        return ResponseValue(-aggregate / self._reference,
                             None if slope is None else -slope / self._reference,
                             reported=self._reported(values))


class MinimumEigenfrequency(_EigenfrequencyBase):
    """Keep the lowest natural frequency above a limit: 1 − λ / limit ≤ 0."""

    name = "eigenfrequency_limit"
    label = "Fundamental frequency (at least)"
    use_when = "When stiffness is the goal but the lowest natural frequency must stay above a limit."
    reference = Eigenfrequency.reference
    order = 45
    roles = (CONSTRAINT_ROLE,)
    params = (
        Param("limit", 0.01, "Eigenvalue limit",
              "Smallest allowed eigenvalue λ = ω² (the square of the angular frequency), in the units set "
              "by the Young's modulus, the mass density and the lengths.",
              min=1e-12, max=1e12, step=0.001, decimals=6),
        MODES_PARAM, SHARPNESS_PARAM,
    )

    def evaluate(self, state, gradient=True):
        aggregate, slope, values = self._aggregate(state, gradient)
        limit = self.settings["limit"]
        return ResponseValue(1.0 - aggregate / limit, None if slope is None else -slope / limit,
                             exact=1.0 - values[0] / limit, reported=self._reported(values))
