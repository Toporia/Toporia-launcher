# library/updaters/beso.py — bi-directional evolutionary structural optimisation.
#
# BESO does not move densities continuously.  Every element is either solid or
# void, and each iteration does three things:
#
#   1. rank the elements by their sensitivity number  α = −dC/dx,
#      which says how much the compliance would rise if the element were removed;
#   2. lower the target volume by the evolution rate, until the budget is reached;
#   3. set every element above a threshold solid and the rest void, with the
#      threshold chosen so the target volume is met exactly.
#
# Elements are added and removed in the same step — that is the "bi-directional"
# part, and what separates BESO from the original ESO, which could only remove.
# "Soft kill" means a removed element keeps a small residual density
# (`void_density`) instead of being deleted, so the stiffness matrix stays
# non-singular and a removed element still has a sensitivity and can come back.
#
# Two details are not optional, and both are the reason naive BESO oscillates:
#
#   Filtering    the ranking is only meaningful on filtered sensitivities.  The
#                model has already applied the filter chain's adjoint, so a run
#                with an empty filter chain will produce checkerboards; use a
#                density or sensitivity filter.
#   Averaging    the sensitivity numbers are averaged over the last
#                `sens_history` iterations.  Without this the threshold chases
#                the flip-flopping of elements it has just switched.
#
# A third control matters just as much once the target volume has been reached
# and the volume stops falling: `ar_max`, the largest fraction of the domain
# that may be ADDED in one iteration.  A bare threshold search is free to swap
# an arbitrary number of elements at a fixed volume, and it does — without this
# limit the exchange phase here moved up to a sixth of the domain in a single
# iteration and intermittently severed the load path, sending the compliance up
# by seven orders of magnitude.  Additions beyond the limit are given back, one
# for one, to the highest-ranked elements the threshold had just removed, so the
# volume is preserved while the design moves gradually.
#
# Convergence is judged on the objective, not on the design: a binary design
# reports a change of ~1 whenever a single element flips, so the engine's own
# tolerance would never fire until the design froze completely.  The criterion
# below is the standard one — the relative change of the objective over two
# consecutive windows of five iterations, applied only once the target volume
# has come down to the budget.
#
# References
# ----------
# X. Huang, Y. M. Xie, "Convergent and mesh-independent solutions for the
# bi-directional evolutionary structural optimization method", Finite Elements
# in Analysis and Design 43 (2007) 1039–1049.
# X. Huang, Y. M. Xie, "Evolutionary Topology Optimization of Continuum
# Structures", Wiley (2010).

from collections import deque

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater

#: Iterations per window of the objective-based convergence test (Huang & Xie use 5).
WINDOW = 5


class BESOUpdater(Updater):
    """Soft-kill BESO: binary designs, evolutionary volume schedule, threshold ranking."""

    name = "beso"
    label = "BESO (soft kill)"
    order = 60
    params = (
        Param("er", 0.02, "Evolution rate",
              "Fraction of the target volume removed each iteration, until the volume "
              "budget is reached. 0.02 needs roughly 35 iterations to reach half the domain.",
              min=0.001, max=0.2, step=0.005, decimals=3),
        Param("ar_max", 0.005, "Addition limit",
              "Largest fraction of the domain that may be added in one iteration. "
              "This is what keeps the constant-volume exchange phase stable: on the "
              "MBB beam, 0.005 settles to within 1% while 0.02 still wanders by 7%.",
              min=0.001, max=0.5, step=0.005, decimals=3),
        Param("void_density", 0.001, "Void density",
              "Residual density of a removed element. Keeps the stiffness matrix "
              "non-singular and lets a removed element be added back later.",
              min=1e-6, max=0.1, step=0.001, decimals=4),
        Param("sens_history", 2, "Sensitivity history",
              "Iterations of sensitivity numbers averaged before ranking. "
              "Averaging is what stops the design oscillating; 1 disables it.",
              min=1, max=10),
        Param("beso_tol", 0.001, "BESO tolerance",
              "Stop when the objective changes by less than this over two consecutive "
              "windows of five iterations, once the volume budget has been reached.",
              min=0.0, max=0.1, step=0.0005, decimals=5),
        Param("start_full", True, "Start from solid",
              "Begin from a full domain and evolve down, as BESO conventionally does. "
              "When off, it starts from the model's initial design and only exchanges "
              "elements at constant volume."),
    )

    # Ranking by −dC/dx assumes the objective falls when material is added, and
    # the threshold search targets the volume budget alone.
    objectives = ("compliance",)
    max_constraints = 0

    def initialize(self, model, settings):
        self.model = model
        self.er = settings["er"]
        self.ar_max = settings["ar_max"]
        self.void_density = settings["void_density"]
        self.tol = settings["beso_tol"]
        self.start_full = settings["start_full"]
        self.lb, self.ub = model.bounds()
        self.limit = model.volume_limit
        self.target = None                                    # current volume target
        self._sensitivities = deque(maxlen=settings["sens_history"])
        self._objectives = []
        self._exchanges = 0                                   # threshold steps taken

    def update(self, x, evaluation, completed):
        self._objectives.append(float(evaluation.objective))
        # α = −dC/dx: large where removing material would cost the most stiffness.
        self._sensitivities.append(np.asarray(-evaluation.objective_gradient, dtype=float))

        if self.target is None:
            if self.start_full:
                solid = np.clip(np.ones_like(x, dtype=float), self.lb, self.ub)
                self.target = self.model.volume_of(solid)
                return solid
            self.target = self.model.volume_of(x)

        self.target = max(self.limit, self.target * (1.0 - self.er))
        design = self._threshold(np.mean(self._sensitivities, axis=0), x)
        self._exchanges += 1
        return design

    def _threshold(self, sensitivity, previous):
        """Binary design whose volume meets the current target.

        The volume falls monotonically as the threshold rises, so a bisection on
        the threshold is the discrete counterpart of OC's bisection on a
        multiplier. Volume is measured through the model, so it accounts for the
        filter chain exactly as the volume budget does for every other updater.
        """
        def design_at(threshold):
            return np.clip(np.where(sensitivity > threshold, 1.0, self.void_density),
                           self.lb, self.ub)

        low, high = float(np.min(sensitivity)), float(np.max(sensitivity))
        if not np.isfinite(low) or not np.isfinite(high) or high - low <= 1e-30:
            # Every element ranks the same, so no ranking exists to act on.
            return design_at(high)

        for _ in range(80):
            threshold = 0.5 * (low + high)
            if self.model.volume_of(design_at(threshold)) > self.target:
                low = threshold
            else:
                high = threshold
            if high - low < 1e-12 * (1.0 + abs(high)):
                break
        return self._limit_additions(design_at(high), previous, sensitivity)

    def _limit_additions(self, design, previous, sensitivity):
        """Give back additions beyond `ar_max`, one for one, to the best removals.

        Everything is indexed in flat C order, consistently and only inside this
        method, so it does not matter what shape or ordering the model's designs
        use.  Skipped on the first threshold step: the incoming design is then
        the model's uniform starting field rather than a binary one, so there is
        no meaningful set of additions to limit.
        """
        if self._exchanges == 0:
            return design

        solid = (design >= 0.5).reshape(-1)
        was_solid = (previous >= 0.5).reshape(-1)
        ranking = sensitivity.reshape(-1)
        added = np.flatnonzero(solid & ~was_solid)
        # At least one addition, so a coarse mesh does not silently turn
        # bi-directional BESO back into one-way ESO.
        cap = max(1, int(self.ar_max * design.size))
        if added.size <= cap:
            return design

        # Give back the weakest additions, and keep solid the strongest of the
        # elements this threshold had just removed, so the count is unchanged.
        revoke = added[np.argsort(ranking[added])][: added.size - cap]
        removed = np.flatnonzero(was_solid & ~solid)
        restore = removed[np.argsort(ranking[removed])[::-1]][: revoke.size]

        flat = design.reshape(-1).copy()
        flat[revoke] = self.void_density
        flat[restore] = 1.0
        return np.clip(flat.reshape(design.shape), self.lb, self.ub)

    def is_converged(self, change):
        """BESO's own criterion: the objective has settled at the target volume.

        `change` is ignored — see the note on binary designs at the top of this
        module.  Returns False while the volume is still being reduced, so a run
        can never be declared converged before it has reached its budget.
        """
        if self.target is None or self.target > self.limit * (1.0 + 1e-9):
            return False
        if len(self._objectives) < 2 * WINDOW:
            return False
        recent = self._objectives[-WINDOW:]
        earlier = self._objectives[-2 * WINDOW:-WINDOW]
        total = sum(abs(value) for value in recent)
        if total == 0.0:
            return False
        return abs(sum(r - e for r, e in zip(recent, earlier))) / total < self.tol
