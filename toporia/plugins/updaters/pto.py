# plugins/updaters/pto.py — proportional topology optimisation (PTO).
#
# Connects to the framework as an Updater.  PTO is the "no optimiser at all"
# baseline: each iteration the whole volume budget is simply handed out to the
# elements in proportion to how hard each one works, with no Lagrange
# multiplier, no linearisation and no step-size rule beyond a move limit.
#
#     target_i  ∝  e_i^q            (e_i = element strain energy, q = exponent)
#     Σ_i target_i · V_i = V_limit  (the budget is spent exactly)
#     x_new = clip( x + clip(target − x, ± move),  lower, upper )
#
# The proportionality constant is found by bisection (the same job as OC's
# multiplier search).  Because it is a scale on e_i^q with the result clipped to
# the element bounds, it reproduces the paper's "cap at solid and redistribute
# the overflow to the others" loop in one pass.  The move limit plays the part of
# the paper's retained material: an element keeps most of what it had.
#
# Element energies.  The paper allocates by strain energy.  An Evaluation carries
# no element energies, only gradients, so this updater uses the objective
# gradient magnitude  e_i = −dC/dx_i  instead.  For compliance under SIMP
# (C = Σ x^p uᵀKu, dC/dx = −p x^(p−1) uᵀKu) that is the strain energy divided
# by x and times p — monotonically related to it, which is why the PTO papers
# treat the two as interchangeable; with a filter chain it is the filtered
# sensitivity.  No framework change was made for this.
#
# PTO is a baseline: it has no convergence theory and it is a fixed-point
# iteration, so it is expected to land somewhat above OC.  Measured on the MBB
# beam (m = 0.4, 200 iterations): the plain scheme (relax 1) flip-flops and ends
# 70-100 % above OC; damping it (relax 0.2, the retained material) and
# concentrating the allocation (q = 3) brings it to about +5 %.  The defaults
# are those; tests/plugins/test_adam_pto_beso_hard.py reports the gap.
#
# Reference
# ---------
# L. Biyikli, A. C. To, "Proportional topology optimization: a new
# non-sensitivity method for solving stress constrained and minimum compliance
# problems and its implementation in MATLAB", PLoS ONE 10 (2015) e0145041.
# http://www.ptomethod.org

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater
from toporia.plugins.shared_params import MOVE


class PTOUpdater(Updater):
    """Proportional topology optimisation: material allocated in proportion to element energy^q."""

    name = "pto"
    reference = (
        'E. Biyikli and A. C. To, "Proportional topology optimization: a new non-sensitivity '
        'method for structural optimization", PLoS ONE 10 (2015) e0145041 (ptomethod.org).'
    )
    label = "Proportional topology optimisation"
    order = 80
    params = (
        MOVE,
        Param("q", 3.0, "Exponent q",
              "Material goes to each element in proportion to its energy raised to q. "
              "Larger concentrates material faster and gives crisper designs, smaller is more cautious.",
              min=0.1, max=5.0, step=0.1, decimals=2),
        Param("relax", 0.2,"Retained material",
              "How far each element moves toward its proportional share per iteration: "
              "1 jumps all the way, smaller keeps more of the old density (the paper's retained "
              "material) and damps the flip-flopping of a fixed-point iteration.",
              min=0.05, max=1.0, step=0.05, decimals=2),
    )

    # The energy proxy (−dC/dx) is only meaningful for compliance, and the single
    # budget is spent by the proportionality constant.
    objectives = ("compliance",)
    max_constraints = 0
    needs_element_densities = True
    schedulable = ("move",)

    def initialize(self, model, settings):
        self.model = model
        self.move = settings["move"]
        self.q = settings["q"]
        self.relax = settings["relax"]
        self.lb, self.ub = model.bounds()

    def update(self, x, evaluation, completed):
        # Energy proxy (see the header); clipped at 0 so a rare positive gradient
        # (a filter artefact) cannot give an element negative material.
        energy = np.maximum(-np.asarray(evaluation.objective_gradient, dtype=float), 0.0)
        shape = energy ** self.q
        top = float(np.max(shape))
        if not np.isfinite(top) or top <= 0.0:
            return x                                       # nothing works: nothing to redistribute
        shape = shape / top

        def design_at(scale):
            """The design for proportionality constant `scale`, inside the move limit and bounds."""
            target = scale * shape
            return np.clip(x + np.clip(self.relax * (target - x), -self.move, self.move), self.lb, self.ub)

        # Volume rises with the constant: bisect for the one that spends the budget.
        low, high = 0.0, 1.0
        while self.model.volume_of(design_at(high)) < self.model.volume_limit and high < 1e12:
            low, high = high, high * 2.0
        for _ in range(100):
            mid = 0.5 * (low + high)
            if self.model.volume_of(design_at(mid)) > self.model.volume_limit:
                high = mid
            else:
                low = mid
            if high - low < 1e-10 * (1.0 + high):
                break
        return design_at(low)
