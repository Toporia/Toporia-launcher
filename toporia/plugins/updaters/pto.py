# plugins/updaters/pto.py — independent sensitivity-proxy PTO variant.
#
# Connects to the framework as an Updater.  PTO is the "no optimiser at all"
# baseline: each iteration the whole volume budget is simply handed out to the
# elements using a negative-sensitivity proxy. This is not the paper's
# element-compliance allocation or filtered redistribution algorithm.
#
#     target_i  ∝  e_i^q            (e_i = max(0, -dC/dx_i), q = exponent)
#     V(x_new) ≈ V_limit           (when reachable under the moving bounds)
#     x_new = clip( x + clip(relax*(target − x), ± move), lower, upper )
#
# The proportionality constant is found by bisection (the same job as OC's
# multiplier search), measuring the model's actual physical volume. The paper
# instead repeatedly filters its remaining material allocation, caps the field
# and redistributes. A move cap and this implementation's relax parameter are
# not equivalent to that loop or its subsequent history blend.
#
# Element energies.  The paper allocates by strain energy.  An Evaluation carries
# no element energies, only gradients, so this updater uses the objective
# gradient magnitude  e_i = −dC/dx_i  instead.  For compliance under SIMP
# (C = Σ x^p uᵀKu, dC/dx = −p x^(p−1) uᵀKu), ignoring Emin, this proxy is
# element compliance times p/x. Since x varies between elements, the weights
# and even their rankings can differ. A filter chain changes them further.
# Batch 3 keeps a native Figure 3 comparison and this mismatch in to-fix.
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
    """PTO-inspired allocation from negative sensitivity, not original PTOc."""

    name = "pto"
    reference = (
        'Independent sensitivity-proxy variant inspired by E. Biyikli and A. C. To, "Proportional topology optimization: a new non-sensitivity '
        'method for structural optimization", PLoS ONE 10 (2015) e0145041 (ptomethod.org).'
        ' Papers: https://doi.org/10.1371/journal.pone.0145041'
    )
    label = "Proportional topology optimisation"
    use_when = (
        "For comparing with proportional topology optimisation. This is a variant, not the original PTOc "
        "(its designs differ by about 20% in compliance on the MBB beam)."
    )
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
