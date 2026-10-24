# plugins/updaters/oc.py — optimality criteria (OC).
#
# The classic top88 update for one material-volume constraint.  Each element
# moves by the square root of its ratio of objective to volume sensitivity,
# scaled by a Lagrange multiplier λ, within a move limit and the element bounds:
#
#     x_new = clip( x · sqrt(−dC/dx ÷ dV/dx ÷ λ),  x ± move,  [lower, upper] )
#
# λ is found by bisection so that the new design uses exactly the allowed
# material.  That search re-filters every candidate, which is why it asks the
# model for volume_of(x) — cheap, no FE solve — rather than for a full evaluation.

import numpy as np

from toporia.framework.parts.updater import Updater
from toporia.plugins.shared_params import MOVE


class OCUpdater(Updater):
    """Optimality criteria with bisection on the volume Lagrange multiplier."""

    name = "oc"
    label = "Optimality criteria"
    reference = (
        'The optimality criteria update of O. Sigmund, "A 99 line topology optimization code'
        ' written in Matlab", Struct. Multidisc. Optim. 21 (2001) 120-127, as written in top88: E.'
        ' Andreassen, A. Clausen, M. Schevenels, B. S. Lazarov, O. Sigmund, "Efficient topology'
        ' optimization in MATLAB using 88 lines of code", Struct. Multidisc. Optim. 43 (2011) 1-16.'
        ' Papers: https://doi.org/10.1007/s001580050176 https://doi.org/10.1007/s00158-010-0594-7'
    )
    order = 10
    params = (MOVE,)
    schedulable = ("move",)

    # OC needs objective and volume sensitivities of opposite sign, and finds a
    # single multiplier: compliance under the volume budget and nothing more.
    objectives = ("compliance",)
    max_constraints = 0
    # The rule moves each element's density on its own (see needs_element_densities).
    needs_element_densities = True

    def initialize(self, model, settings):
        self.model = model
        self.move = settings["move"]
        self.lb, self.ub = model.bounds()

    def update(self, x, evaluation, completed):
        move = self.move
        # Ratio of objective to volume sensitivity.  Where the volume gradient is
        # exactly zero (an element whose whole neighbourhood is pinned) the ratio
        # is taken as 0, which only pushes that element toward its lower bound.
        ratio = np.divide(-evaluation.objective_gradient, evaluation.volume_gradient,
                          out=np.zeros_like(evaluation.objective_gradient),
                          where=evaluation.volume_gradient != 0)

        l1, l2 = 0.0, 1e9
        while (l2 - l1) / (l1 + l2 + 1e-12) > 1e-3:
            lm = 0.5 * (l1 + l2)
            candidate = np.maximum(self.lb, np.maximum(
                x - move,
                np.minimum(self.ub, np.minimum(
                    x + move,
                    x * np.sqrt(np.maximum(0.0, ratio / lm))
                ))
            ))
            if self.model.volume_of(candidate) > self.model.volume_limit:
                l1 = lm
            else:
                l2 = lm
        return candidate
