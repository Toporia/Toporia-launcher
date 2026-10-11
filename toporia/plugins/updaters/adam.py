# plugins/updaters/adam.py — Adam on the design variables, volume budget as an augmented Lagrangian.
#
# Connects to the framework as an Updater: it receives an Evaluation (objective,
# volume, their gradients) and returns the next design.  It is the updater a
# neural reparameterisation needs (the design variables are then network
# weights, the budget a penalty rather than a bound, as in TOuNN) and it also
# works on plain element densities, which is how it is tested here.
#
# Algorithm
# ---------
# The volume constraint  g(x) = V(x)/V_limit − 1 ≤ 0  is folded into the
# objective by the augmented Lagrangian for inequalities (Nocedal & Wright,
# Numerical Optimization, §17.4):
#
#     L(x) = f(x)/f₀ + (1/2μ)·( max(0, λ + μ·g)² − λ² )
#     ∇L   = ∇f/f₀ + max(0, λ + μ·g)·∇V/V_limit
#
# with the objective divided by its first value f₀, so the learning rate and the
# penalty mean the same thing on every problem whatever the units of compliance.
# Each iteration takes one Adam step on ∇L (Kingma & Ba, ICLR 2015: bias-corrected
# first and second moment estimates, step  lr·m̂/(√v̂ + ε)) and then the
# multiplier update  λ ← max(0, λ + μ·g).  A plain quadratic penalty (what TOuNN
# calls the penalty method) is the same thing with λ held at 0: set
# "Multiplier update" off.  The learning rate decays geometrically, which is what
# lets the run settle: Adam's step is ≈ lr per variable however small the
# gradient, so with a constant rate the design change never falls below any
# tolerance.
#
# Bounds: CLIPPING, not a sigmoid reparameterisation.  Reasons: (1) the box is
# per element and includes pinned elements (lower = upper), which clipping
# honours exactly and a sigmoid cannot; (2) the sigmoid's gradient vanishes at
# saturation, so a variable that has gone solid or void almost never returns —
# a bias a baseline should not add — and the design never reaches its bound
# exactly; (3) projected Adam is what runs when the variables are network
# weights too, where the bounds are infinite and the clip does nothing.  The cost
# is that a variable pressed against a bound keeps accumulating moments; at the
# decaying rates used here that was not observed to matter.
#
# The budget is only approximately enforced during the run (a penalty method
# cannot do better); the multiplier drives the violation to the order of the
# Adam step size, which the check's 1 % volume tolerance accepts.
#
# References
# ----------
# D. P. Kingma, J. Ba, "Adam: a method for stochastic optimization", ICLR 2015
# (arXiv:1412.6980).
# A. Chandrasekhar, K. Suresh, "TOuNN: topology optimization using neural
# networks", Structural and Multidisciplinary Optimization 63 (2021) 1135–1149.
# J. Nocedal, S. J. Wright, "Numerical Optimization", Springer (2006), §17.4.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater


class AdamUpdater(Updater):
    """Adam steps on the design, the volume budget as an augmented-Lagrangian term."""

    name = "adam"
    label = "Adam (augmented Lagrangian)"
    order = 70
    params = (
        Param("lr", 0.05, "Learning rate",
              "Adam's step per variable at the first iteration, in design units "
              "(0.05 moves a density by about 5 % of its range). It decays by the factor below.",
              min=0.0001, max=1.0, step=0.005, decimals=4),
        Param("lr_decay", 0.995, "Learning-rate decay",
              "The learning rate is multiplied by this each iteration. 1 keeps it constant, "
              "and then the design never settles under the engine's tolerance.",
              min=0.9, max=1.0, step=0.005, decimals=3),
        Param("beta1", 0.5, "β₁",
              "Decay of the first-moment (momentum) estimate. Adam's usual 0.9 carries the design "
              "past the volume budget (7-9 % over on the MBB beam, measured); 0.5 keeps it on.",
              min=0.0, max=0.999, step=0.01, decimals=3),
        Param("beta2", 0.999, "β₂", "Decay of the second-moment (step-scaling) estimate.",
              min=0.0, max=0.9999, step=0.001, decimals=4),
        Param("penalty", 3.0, "Penalty μ",
              "Weight of the volume term, on the normalised constraint V/V_limit − 1 "
              "and the normalised objective. Larger holds the budget tighter, "
              "at the price of a stiffer problem.",
              min=0.1, max=1000.0, step=1.0, decimals=1),
        Param("multiplier", True, "Multiplier update",
              "Augmented Lagrangian: update a multiplier on the volume constraint each iteration. "
              "Off gives the plain quadratic penalty, which leaves a steady volume violation."),
    )

    # The gradient step itself is objective-agnostic, but it is only exercised on
    # compliance; the budget is the only constraint it knows about.
    objectives = ("compliance",)
    max_constraints = 0
    schedulable = ("lr",)

    def initialize(self, model, settings):
        self.model = model
        self.lr = settings["lr"]
        self.decay = settings["lr_decay"]
        self.beta1 = settings["beta1"]
        self.beta2 = settings["beta2"]
        self.mu = settings["penalty"]
        self.use_multiplier = settings["multiplier"]
        self.lb, self.ub = model.bounds()
        self.limit = model.volume_limit
        self.scale = None             # f₀, the first objective value
        self.lam = 0.0                # the volume multiplier λ ≥ 0
        self.m = self.v = None        # Adam's moment estimates
        self.t = 0

    def update(self, x, evaluation, completed):
        if self.scale is None:
            self.scale = max(abs(float(evaluation.objective)), 1e-30)
            self.m = np.zeros_like(x, dtype=float)
            self.v = np.zeros_like(x, dtype=float)

        g = float(evaluation.volume) / self.limit - 1.0
        active = max(0.0, self.lam + self.mu * g)        # the inequality's penalty slope
        grad = (np.asarray(evaluation.objective_gradient, dtype=float) / self.scale
                + active * np.asarray(evaluation.volume_gradient, dtype=float) / self.limit)
        if self.use_multiplier:
            self.lam = active

        self.t += 1
        self.m = self.beta1 * self.m + (1.0 - self.beta1) * grad
        self.v = self.beta2 * self.v + (1.0 - self.beta2) * grad * grad
        m_hat = self.m / (1.0 - self.beta1 ** self.t)
        v_hat = self.v / (1.0 - self.beta2 ** self.t)
        step = self.lr * self.decay ** (self.t - 1) * m_hat / (np.sqrt(v_hat) + 1e-8)
        return np.clip(x - step, self.lb, self.ub)

    def set_parameter(self, name, value):
        """A schedule may change the learning rate during a run."""
        if name == "lr":
            self.lr = float(value)
