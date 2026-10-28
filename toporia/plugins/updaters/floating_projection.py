"""Floating-projection OC, written from Huang's equations, not copied code.

Equations 9, 12-16 in arXiv:2006.04306: damp sensitivities, take an OC ratio
step, and project with a threshold that preserves volume. Increase beta after
mean design change falls below the stage tolerance. Contrary to the old backlog
description, the published method DOES use internal beta continuation.

Modular adaptation: smoothing and physical interpolation belong to the model,
so this updater does not filter the trial design a second time. The exact model
volume is checked after projection and move/bound clipping, including pinned
elements. This is not the paper's separate smooth-boundary reconstruction and
reanalysis, nor a guarantee of an exactly binary physical field after filtering.
"""

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.updater import Updater
from toporia.plugins.filters.heaviside import HeavisideFilter
from toporia.plugins.shared_params import MOVE


class FloatingProjectionUpdater(Updater):
    """OC ratio update with a mass-preserving floating projection of its trial."""

    name = "floating_projection"
    label = "Floating projection (FPTO)"
    use_when = (
        "An OC-like update that drives the design to 0/1 while keeping the volume; for crisp designs "
        "without a Heaviside filter."
    )
    order = 65
    reference = (
        'X. Huang, "Smooth topological design of structures using the floating projection", '
        'Engineering Structures 208 (2020) 110330; "On smooth or 0/1 designs of the fixed-mesh '
        'element-based topology optimization", Advances in Engineering Software 151 (2021) 102942. '
        'Papers: https://doi.org/10.1016/j.engstruct.2020.110330 '
        'https://doi.org/10.1016/j.advengsoft.2020.102942'
    )
    objectives = ("compliance", "thermal_compliance")
    needs_element_densities = True
    params = (
        MOVE,
        Param("fp_beta_max", 8.0, "Final FP sharpness",
              "Final internal projection sharpness. Increased by one after a stage settles.",
              min=1.0, max=64.0, step=1.0, decimals=1),
        Param("fp_stage_tol", 0.001, "FP stage tolerance",
              "Mean change of free design variables below which sharpness increases.",
              min=1e-6, max=0.05, step=0.001, decimals=5),
    )

    def initialize(self, model, settings):
        self.model = model
        self.lb, self.ub = model.bounds()
        self.free = self.ub > self.lb
        self.move = settings["move"]
        self.beta_max = settings["fp_beta_max"]
        self.stage_tol = settings["fp_stage_tol"]
        if (not np.all(np.isfinite([self.move, self.beta_max, self.stage_tol]))
                or self.move <= 0 or self.beta_max < 1 or self.stage_tol <= 0):
            raise ValueError("FPTO requires positive move/tolerance and fp_beta_max >= 1")
        self.beta = 1e-6
        self.used_beta = 0.0
        self.previous_gradient = None
        self.projection = HeavisideFilter(eta_mode="volume_preserving")

    def _project(self, trial):
        out = np.array(trial, copy=True)
        if self.beta > 1e-4 and np.any(self.free):
            self.projection.beta = self.beta
            out[self.free] = self.projection.forward(out[self.free])
        return out

    def update(self, x, evaluation, completed):
        gradient = np.asarray(evaluation.objective_gradient)
        if self.previous_gradient is not None:
            gradient = 0.5 * (gradient + self.previous_gradient)
        self.previous_gradient = gradient.copy()
        ratio = np.divide(-gradient, evaluation.volume_gradient,
                          out=np.zeros_like(gradient), where=evaluation.volume_gradient > 0)
        ratio = np.maximum(ratio, 0.0)
        scale = np.max(ratio[self.free]) if np.any(self.free) else 0.0
        if scale > 0:
            ratio = ratio / scale
        lower, upper = np.maximum(self.lb, x - self.move), np.minimum(self.ub, x + self.move)

        def candidate(multiplier):
            trial = np.clip(np.maximum(x, 1e-3) * ratio * multiplier, self.lb, self.ub)
            return np.clip(self._project(trial), lower, upper)

        lo, hi = 0.0, 1.0
        best = candidate(lo)
        # If the move box is entirely above the budget, take its minimum;
        # subsequent iterations restore feasibility without breaking the move.
        if self.model.volume_of(best) <= self.model.volume_limit:
            for _ in range(60):
                trial = candidate(hi)
                if self.model.volume_of(trial) > self.model.volume_limit:
                    break
                best = trial
                hi *= 2.0
            else:
                hi = lo  # all reachable candidates are feasible
            for _ in range(45):
                if hi <= lo:
                    break
                mid = 0.5 * (lo + hi)
                trial = candidate(mid)
                if self.model.volume_of(trial) > self.model.volume_limit:
                    hi = mid
                else:
                    lo, best = mid, trial
                if hi - lo < 1e-9 * max(1.0, hi):
                    break

        self.used_beta = self.beta
        change = np.mean(np.abs(best[self.free] - x[self.free])) if np.any(self.free) else 0.0
        if change < self.stage_tol:
            self.beta = min(self.beta_max, self.beta + 1.0)
        return best

    def continuing(self):
        # The last iteration must actually use beta_max before ordinary engine
        # tolerance is allowed to stop the run.
        return self.used_beta < self.beta_max

    def report(self):
        finished = not self.continuing()
        return {"beta": self.used_beta, "beta_target": self.beta_max,
                "continuation_finished": finished, "finished": finished,
                "message": (f"FP continuation {'finished' if finished else 'unfinished'}: "
                            f"used beta {self.used_beta:g}, target {self.beta_max:g}")}
