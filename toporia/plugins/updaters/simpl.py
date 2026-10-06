# library/updaters/simpl.py — entropic mirror descent on a latent variable (SiMPL).
#
# The design is not updated directly.  It is carried as a latent variable
#
#     w = logit(x) = ln( x / (1 − x) ),
#
# a gradient step is taken in w, and the design comes back through the sigmoid
#
#     x = 1 / (1 + exp(−w)).
#
# Because the sigmoid maps the whole real line into (0, 1), every iterate
# satisfies its bounds by construction — there is no clipping to the box and no
# element can get stuck at a bound with a gradient still pushing on it.  This is
# mirror descent with the (negative) Fermi–Dirac entropy as the mirror map; the
# resulting non-symmetric distance is a Bregman divergence, and the logit/sigmoid
# pair is what that choice of entropy produces.
#
# The volume budget is imposed exactly as optimality criteria imposes it: one
# multiplier, found by bisection.  Unlike OC, the multiplier is allowed to be
# zero, so a volume budget that is not yet binding simply does not act:
#
#     x(λ) = sigmoid( w − α·( ĝ + λ·v̂ ) )      λ ≥ 0, chosen so V(x) ≤ V_limit
#
# Two deliberate departures from the paper, both noted because they change what
# a comparison measures:
#
#   1. The paper discretises the latent variable in its own finite-element
#      space, which is what makes the method pointwise-feasible for high-order
#      elements.  Toporia's designs are element-wise constants, so the update
#      here is the pointwise form of the same rule.
#   2. The gradients are normalised by their largest magnitude before the step,
#      so `step` means "how far in logit units" and is independent of the units
#      of the objective.  Without this, a usable step size would differ by
#      orders of magnitude between problems and nothing could be swept.
#
# The growing step size the method relies on also needs a safeguard, or late
# iterations keep flipping elements and the design never settles: with a step
# that only grows, this updater was still reporting a design change of 0.29
# after 150 iterations on the MBB beam.  The rule here is the usual one for
# adaptive first-order methods — grow the step while the objective improves,
# halve it on any iteration that does not.
#
# What this implementation actually does, measured
# ------------------------------------------------
# MBB beam, 20x60 elements, volume fraction 0.5, density filter rmin=1.5,
# against the optimality-criteria updater on the same model:
#
#     iteration      50      100      150      221
#     OC         220.74   219.26   218.75   218.53
#     SiMPL      220.99   220.56   219.79   218.70
#
# So it converges to the same design — within 0.1% of OC's compliance, with a
# marginally crisper density field — but it does NOT reproduce the paper's
# reported advantage over OC and MMA at equal iteration count.  Whether that is
# the element-wise reduction, the step-size rule here, or this problem is an
# open question, and exactly the kind of question Toporia exists to settle.
# Treat the numbers above as a regression baseline, not as a result about SiMPL.
#
# Reference
# ---------
# B. Keith, D. Kim, B. S. Lazarov, T. M. Surowiec, "A simple introduction to
# the SiMPL method for density-based topology optimization", Structural and
# Multidisciplinary Optimization 68 (2025); arXiv:2411.19421.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater

# Densities are pulled this far inside (0, 1) before the logit, which is
# infinite at both ends.  1e-9 keeps |w| below ~21: far enough to act like a
# bound, close enough that exp() cannot overflow.
_EDGE = 1e-9

#: Relative objective improvement below which the step is treated as having
#: stopped paying off, and is halved.  See SiMPLUpdater._adapt.
_FLAT = 1e-6


def _logit(x):
    return np.log(x) - np.log1p(-x)


def _sigmoid(w):
    # expit, written out: the two branches keep exp() away from overflow for
    # large |w|, which happens as soon as the multiplier search expands.
    out = np.empty_like(w, dtype=float)
    positive = w >= 0.0
    out[positive] = 1.0 / (1.0 + np.exp(-w[positive]))
    tail = np.exp(w[~positive])
    out[~positive] = tail / (1.0 + tail)
    return out


class SiMPLUpdater(Updater):
    """Mirror descent in the logit of the density, under the volume budget."""

    name = "simpl"
    label = "Mirror descent (SiMPL)"
    order = 30
    params = (
        Param("step", 1.0, "Step size",
              "First step, in logit units: 1 is enough to move a mid-grey element "
              "most of the way toward solid or void.",
              min=0.01, max=100.0, step=0.1, decimals=2),
        Param("step_growth", 1.2, "Step growth",
              "The step is multiplied by this each iteration. Growing it is what makes "
              "the method converge quickly; 1.0 keeps it constant.",
              min=1.0, max=2.0, step=0.05, decimals=2),
        Param("step_max", 64.0, "Step limit",
              "Upper limit of the growing step, so late iterations cannot flip the whole design.",
              min=0.1, max=10000.0, step=1.0, decimals=1),
    )

    # The update rule itself is not restricted to compliance — it needs only a
    # gradient — but it is only tested against compliance, so that is what it
    # advertises.  Widen this list when a second objective is actually exercised.
    objectives = ("compliance",)
    max_constraints = 0

    def initialize(self, model, settings):
        self.model = model
        self.step = settings["step"]
        self.growth = settings["step_growth"]
        self.step_cap = settings["step_max"]
        self.step_floor = 1e-3 * settings["step"]
        self.lb, self.ub = model.bounds()
        self.limit = model.volume_limit
        self._previous_objective = None

    def update(self, x, evaluation, completed):
        step = self._adapt(evaluation.objective)
        latent = _logit(np.clip(x, _EDGE, 1.0 - _EDGE))

        objective_direction = _normalised(evaluation.objective_gradient)
        volume_direction = _normalised(evaluation.volume_gradient)

        def design_at(multiplier):
            moved = latent - step * (objective_direction + multiplier * volume_direction)
            return np.clip(_sigmoid(moved), self.lb, self.ub)

        return design_at(self._multiplier(design_at))

    def _adapt(self, objective):
        """Return this iteration's step: grown while the objective still improves.

        "Still improves" means by more than `_FLAT` in relative terms.  Halving
        on an outright worsening alone is not enough: once the objective has
        settled, a large step keeps saturated elements flipping between the two
        ends of the sigmoid, which costs nothing in objective but keeps the
        design change the engine watches from ever reaching its tolerance.
        Collapsing the step on a plateau is what lets the run stop on its own.
        """
        previous = self._previous_objective
        self._previous_objective = objective
        if previous is None:
            return self.step

        improvement = (previous - objective) / max(abs(previous), 1e-30)
        if improvement > _FLAT:
            self.step = min(self.growth * self.step, self.step_cap)
        else:
            self.step = max(0.5 * self.step, self.step_floor)
        return self.step

    def _multiplier(self, design_at):
        """Smallest λ ≥ 0 whose design fits the volume budget.

        The volume decreases monotonically in λ, so λ=0 is the answer whenever
        the budget is not binding — the case OC cannot express, since its
        multiplier is always active.
        """
        if self.model.volume_of(design_at(0.0)) <= self.limit:
            return 0.0

        low, high = 0.0, 1.0
        for _ in range(60):      # expand until the budget is met
            if self.model.volume_of(design_at(high)) <= self.limit:
                break
            low, high = high, high * 2.0
        else:
            # Unreachable budget (the fixed-solid elements alone exceed it).
            # Return the tightest multiplier tried rather than loop forever;
            # the engine's feasibility check reports the violation.
            return high

        for _ in range(60):
            multiplier = 0.5 * (low + high)
            if self.model.volume_of(design_at(multiplier)) > self.limit:
                low = multiplier
            else:
                high = multiplier
            if high - low < 1e-10 * (1.0 + high):
                break
        return high


def _normalised(gradient):
    """Gradient scaled to a largest magnitude of 1, so `step` is in logit units."""
    scale = float(np.max(np.abs(gradient)))
    if not np.isfinite(scale) or scale == 0.0:
        return np.zeros_like(gradient, dtype=float)
    return gradient / scale
