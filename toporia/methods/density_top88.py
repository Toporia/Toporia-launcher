# methods/density_top88.py — SIMP density topology optimisation
#
# Algorithm overview (for an engineer unfamiliar with topology optimisation):
#
#   Goal: distribute a fixed amount of material inside the bracket domain to
#         minimise structural compliance (= maximise stiffness).
#
#   Design variable: x[i,j] ∈ [0,1] — density of element (i,j).
#                    0 = void (no material),  1 = solid.
#
#   SIMP model: element stiffness E(ρ) = Emin + ρ^p × (E0−Emin)
#     The penalty exponent p (default 3) makes intermediate densities costly,
#     driving the solution toward black-and-white designs.
#
#   Each iteration:
#     1. FEA  → compute displacements and compliance sensitivities
#     2. Pipeline adjoint → map sensitivities back to design variables
#     3. OC update → adjust densities toward the optimum (binary search on λ)
#
# This implementation closely follows the 99-line top88 MATLAB code by
# Andreassen et al. (2011).

import numpy as np

from .base import OptimizationMethod, solve_fea
from .filter_chain import DensityFilterPipeline


class DensityTop88Method(OptimizationMethod):

    def initialize(self, problem, config):
        self.problem   = problem
        self.config    = config
        self.iteration = 0
        self.objective = np.inf
        self.change    = np.inf

        n_total   = problem.nelx * problem.nely
        n_passive = int(np.sum(problem.passive_elements))
        if n_passive > config.volfrac * n_total:
            raise ValueError(
                f"Infeasible volume fraction: passive (forced-solid) elements already "
                f"fill {n_passive / n_total:.1%} of the domain, which exceeds "
                f"volfrac={config.volfrac:.1%}. Raise volfrac or reduce the passive region."
            )

        # Initialise design variables to the target volume fraction.
        self.x = np.full((problem.nely, problem.nelx), config.volfrac)
        self.x[problem.passive_elements] = 1.0
        self.x[problem.void_elements]    = 0.0

        self.pipeline = DensityFilterPipeline(problem, config)
        self.x_phys = self.pipeline.physical_density(self.x)

    # ── Main optimisation step ────────────────────────────────────────────────

    def step(self):
        cfg, problem = self.config, self.problem

        # ── 1. FEA ────────────────────────────────────────────────────────────
        _, ce, self.objective = solve_fea(problem, cfg, self.x_phys)

        # Raw compliance and volume sensitivities w.r.t. physical density.
        dc = -cfg.penal * (cfg.E0 - cfg.Emin) * self.x_phys ** (cfg.penal - 1.0) * ce
        dv = np.ones_like(self.x)

        # ── 2. Sensitivity correction via the explicit filter pipeline ────────
        dc, dv = self.pipeline.sensitivities(dc, dv)
        self.pipeline.step(self.iteration)

        # ── 3. OC update: binary search for the Lagrange multiplier ──────────
        old = self.x.copy()
        l1, l2 = 0.0, 1e9
        while (l2 - l1) / (l1 + l2 + 1e-12) > 1e-3:
            lm        = 0.5 * (l1 + l2)
            candidate = np.maximum(0.0, np.maximum(
                self.x - cfg.move,
                np.minimum(1.0, np.minimum(
                    self.x + cfg.move,
                    self.x * np.sqrt(np.maximum(0.0, -dc / dv / lm))
                ))
            ))
            candidate[problem.passive_elements] = 1.0
            candidate[problem.void_elements]    = 0.0
            candidate_phys = self.pipeline.physical_density(candidate)
            if np.sum(candidate_phys) > cfg.volfrac * (problem.nelx * problem.nely):
                l1 = lm
            else:
                l2 = lm

        self.x      = candidate
        self.x_phys = self.pipeline.physical_density(self.x)
        self.change  = float(np.max(np.abs(self.x - old)))
        self.iteration += 1

    # ── Convergence and output ────────────────────────────────────────────────

    def has_converged(self):
        return self.iteration >= self.config.max_iter or self.change < self.config.tol

    def get_density(self):   return self.x_phys
    def get_objective(self): return self.objective
    def get_iteration(self): return self.iteration
