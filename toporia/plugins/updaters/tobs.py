# plugins/updaters/tobs.py — TOBS: topology optimisation of binary structures.
#
# Connects to the framework as an Updater: it receives an Evaluation (objective,
# volume and their gradients) and returns the next design.  Like BESO it keeps
# every element strictly void or solid (`needs_element_densities`), but it does
# not rank elements by a threshold.  It solves a small optimisation problem
# instead:
#
#   1. linearise the objective and the volume at the current binary design;
#   2. choose, for every element, a flip  Δ ∈ {−1, 0, +1}  (solid→void, keep,
#      void→solid) so that the LINEARISED objective is as low as possible,
#      subject to the linearised volume staying under a target and at most a
#      fraction β of the elements flipping — an integer linear program (ILP),
#      solved to optimality by HiGHS through `scipy.optimize.milp`;
#   3. apply the flips, re-evaluate, repeat.
#
# Two safeguards make the linearisation trustworthy, and they are the method's
# two named parameters:
#
#   ε  constraint relaxation: the volume target moves toward the budget by at
#      most ε per iteration (a fraction of the full domain's volume, so 0.015 is
#      1.5 per cent of it).  Starting from a full domain this is a gradual
#      descent to the budget; once there, the target IS the budget and the ILP
#      is free to trade material between places.  Without the relaxation the
#      first step would try to remove half the structure on a linear model.
#   β  flip limit (truncation): the largest fraction of the elements that may
#      change state in one iteration.  It is the move limit of a binary method.
#      The ILP is only feasible if the cap lets the volume follow its target,
#      so the cap actually used is never below ε.
#
# As in the 101-line code the objective sensitivities are averaged with those of
# the previous iteration (a mean of two, as BESO does over `sens_history`), which
# damps the flip-flopping of elements switched on and off in turn.  The model has
# already applied the filter chain's adjoint, so use a density or sensitivity
# filter (an empty chain gives checkerboards, as for BESO).
#
# Convergence is judged on the objective, not on the design (a binary design's
# change is ~1 whenever one element flips): the relative change of the objective
# over two windows of five iterations, only once the volume target has reached
# the budget — the same criterion BESO uses.
#
# References
# ----------
# L. F. N. Sivapuram, R. Picelli, "Topology optimization of binary structures
# using Integer Linear Programming", Finite Elements in Analysis and Design 139
# (2018) 49–61.
# R. Picelli, S. Sivapuram, Y. M. Xie, "A 101-line MATLAB code for topology
# optimization using binary variables and integer programming", Structural and
# Multidisciplinary Optimization 63 (2021) 935–954.
# https://doi.org/10.1007/s00158-020-02719-9

from collections import deque

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater

#: Iterations per window of the objective-based convergence test (as in BESO).
WINDOW = 5


class TOBSUpdater(Updater):
    """Sequential integer linear programming on binary elements (TOBS)."""

    name = "tobs"
    reference = (
        'R. Sivapuram and R. Picelli, Finite Elem. Anal. Des. 139 (2018) 49-61; R. Picelli, '
        'R. Sivapuram and Y. M. Xie, "A 101-line MATLAB code for topology optimization using '
        'binary variables and integer programming", Struct. Multidisc. Optim. 63 (2021) '
        '935-954. The integer program is solved with HiGHS through scipy.optimize.milp.'
        ' Papers: https://doi.org/10.1016/j.finel.2017.10.006 https://doi.org/10.1007/s00158-020-02719-9'
    )
    label = "TOBS (integer LP)"
    use_when = (
        "For strictly binary designs: each step solves a small integer linear program under the volume "
        "budget."
    )
    order = 65
    params = (
        Param("epsilon", 0.015, "Constraint relaxation (ε)",
              "Largest change of the volume target per iteration, as a fraction of "
              "the full-domain volume (0.015 = 1.5 per cent of the domain). Larger reaches the "
              "budget sooner but trusts the linearisation further.",
              min=0.001, max=0.2, step=0.005, decimals=3),
        Param("beta", 0.03, "Flip limit (β)",
              "Largest fraction of the elements that may change between void and solid "
              "in one iteration. Smaller is steadier, larger explores faster; it is "
              "never taken below ε.",
              min=0.005, max=0.5, step=0.005, decimals=3),
        Param("average", True, "Average sensitivities",
              "Average the objective sensitivities with those of the previous iteration, "
              "as the 101-line code does. Damps oscillation; off uses the latest only."),
        Param("tobs_tol", 0.001, "TOBS tolerance",
              "Stop when the objective changes by less than this over two consecutive "
              "windows of five iterations, once the volume budget has been reached.",
              min=0.0, max=0.1, step=0.0005, decimals=5),
        Param("start_full", True, "Start from solid",
              "Begin from a full domain and descend to the budget, as the 101-line code "
              "does. When off, the model's initial design is thresholded at its midpoint."),
    )

    # Compliance only: the linearised problem takes the objective's gradient as
    # the cost of each flip and the volume budget as its single constraint row.
    objectives = ("compliance",)
    max_constraints = 0
    needs_element_densities = True

    def initialize(self, model, settings):
        self.model = model
        self.epsilon = settings["epsilon"]
        self.beta = settings["beta"]
        self.tol = settings["tobs_tol"]
        self.start_full = settings["start_full"]
        self.lb, self.ub = model.bounds()
        self.limit = model.volume_limit
        # ε is a fraction of the full domain; volume has the budget's own units.
        self.step_limit = self.epsilon * model.volume_of(np.array(self.ub, dtype=float))
        self.target = None                                    # current volume target
        self._sensitivities = deque(maxlen=2 if settings["average"] else 1)
        self._objectives = []
        self.last_status = None                               # HiGHS status, for inspection

    def update(self, x, evaluation, completed):
        self._objectives.append(float(evaluation.objective))
        self._sensitivities.append(np.asarray(evaluation.objective_gradient, dtype=float))

        lb = np.broadcast_to(self.lb, x.shape)
        ub = np.broadcast_to(self.ub, x.shape)
        if self.target is None and self.start_full:
            # The ILP only moves a binary design, so first make one: all solid.
            solid_design = np.array(ub, dtype=float)
            self.target = self.model.volume_of(solid_design)
            return solid_design

        solid = x > 0.5 * (lb + ub)
        if self.target is None:
            volume = self.model.volume_of(np.where(solid, ub, lb))
        else:
            volume = float(evaluation.volume)
        # Relaxed target: head for the budget but never further than ε at a time.
        self.target = float(np.clip(self.limit, volume - self.step_limit, volume + self.step_limit))

        flips = self._solve(solid, lb, ub, volume, np.mean(self._sensitivities, axis=0),
                            evaluation.volume_gradient)
        new_solid = solid ^ flips.reshape(solid.shape)
        return np.where(new_solid, ub, lb)

    def _solve(self, solid, lb, ub, volume, df, dv):
        """Boolean flip mask from one integer LP on the linearised problem.

        Variables are the flips Δ per element in state units (0 void, 1 solid),
        so a solid element may only go to −1 and a void one to +1.  Gradients
        are converted from design units with the element's own (ub − lb).
        """
        span = (ub - lb).reshape(-1)
        s = solid.reshape(-1)
        c = df.reshape(-1) * span
        scale = np.max(np.abs(c))
        c = c / scale if scale > 0 else c                     # HiGHS is happier near unit costs
        a_volume = dv.reshape(-1) * span
        n = s.size
        free = span > 0                                       # fixed elements cannot flip
        lower = np.where(s, -1.0, 0.0) * free
        upper = np.where(s, 0.0, 1.0) * free
        sign = np.where(s, -1.0, 1.0)                         # |Δ| = sign·Δ for either state
        rows = csr_matrix(np.vstack([a_volume, sign]))

        # The flip cap must at least let the volume follow its target, or the
        # ILP is infeasible; if it still is (uneven elements), widen and retry.
        cap = float(np.ceil(max(self.beta, self.epsilon) * n))
        for _ in range(2):
            constraints = LinearConstraint(rows, [-np.inf, -np.inf], [self.target - volume, cap])
            result = milp(c, constraints=constraints, integrality=np.ones(n),
                          bounds=Bounds(lower, upper), options={"time_limit": 60.0})
            self.last_status = result.status
            if result.x is not None:
                return np.round(result.x).astype(int) != 0
            cap *= 2.0
        return np.zeros(n, dtype=bool)                        # nothing feasible: stay put

    def is_converged(self, change):
        """The objective has settled at the budget; `change` is ignored (binary design)."""
        if self.target is None or self.target > self.limit * (1.0 + 1e-9):
            return False
        if len(self._objectives) < 2 * WINDOW:
            return False
        recent = self._objectives[-WINDOW:]
        earlier = self._objectives[-2 * WINDOW:-WINDOW]
        total = sum(abs(value) for value in recent)
        if total == 0.0:
            return False
        return abs(sum(r - e for r, e in zip(recent, earlier, strict=True))) / total < self.tol
