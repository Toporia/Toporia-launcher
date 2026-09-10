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

from toporia.core.contract import OBJECTIVE, Capabilities, OptimizationMethod
from toporia.library.fe.q4_plane_stress import solve_fea

from ._shared_params import MOVE, PENAL
from .filter_chain import DensityFilterPipeline


class DensityTop88Method(OptimizationMethod):

    name = "density"
    label = "SIMP density (OC)"
    order = 10
    params = (PENAL, MOVE)
    capabilities = Capabilities(variable_kind="density", accepts_filters=True)

    def initialize(self, problem, solver):
        self.problem   = problem
        self.solver    = solver
        self.settings  = self.resolve_params(solver)   # this method's Param values
        self.objective = np.inf
        self.change    = np.inf

        n_total   = problem.nelx * problem.nely
        n_passive = int(np.sum(problem.passive_elements))
        if n_passive > problem.scenario.volfrac * n_total:
            raise ValueError(
                f"Infeasible volume fraction: passive (forced-solid) elements already "
                f"fill {n_passive / n_total:.1%} of the domain, which exceeds "
                f"volfrac={problem.scenario.volfrac:.1%}. Raise volfrac or reduce the passive region."
            )

        # Per-element bounds replace the passive/void masks: clipping to them is
        # equivalent to overwriting after every update, but cannot be forgotten.
        self.lb, self.ub = problem.lower_bound, problem.upper_bound

        # Initialise design variables to the target volume fraction.
        self.x = np.clip(np.full((problem.nely, problem.nelx), problem.scenario.volfrac), self.lb, self.ub)

        self.pipeline = DensityFilterPipeline(problem, solver)
        self.x_phys = self.pipeline.physical_density(self.x)

    # ── Main optimisation step ────────────────────────────────────────────────

    def step(self, iteration):
        problem = self.problem
        sc = problem.scenario   # material and volume target
        # Number of iterations already completed; continuation schedules count from 0.
        completed = iteration - 1

        # ── 1. FEA ────────────────────────────────────────────────────────────
        penal, move = self.settings["penal"], self.settings["move"]
        _, ce, self.objective = solve_fea(problem, self.x_phys, penal)

        # Raw compliance and volume sensitivities w.r.t. physical density.
        dc = -penal * (sc.E0 - sc.Emin) * self.x_phys ** (penal - 1.0) * ce
        dv = np.ones_like(self.x)

        # ── 2. Sensitivity correction via the explicit filter pipeline ────────
        dc, dv = self.pipeline.sensitivities(dc, dv)
        self.pipeline.step(completed)

        # ── 3. OC update: binary search for the Lagrange multiplier ──────────
        old = self.x.copy()
        l1, l2 = 0.0, 1e9
        while (l2 - l1) / (l1 + l2 + 1e-12) > 1e-3:
            lm        = 0.5 * (l1 + l2)
            candidate = np.maximum(self.lb, np.maximum(
                self.x - move,
                np.minimum(self.ub, np.minimum(
                    self.x + move,
                    self.x * np.sqrt(np.maximum(0.0, -dc / dv / lm))
                ))
            ))
            candidate_phys = self.pipeline.physical_density(candidate)
            if np.sum(candidate_phys) > sc.volfrac * (problem.nelx * problem.nely):
                l1 = lm
            else:
                l2 = lm

        self.x      = candidate
        self.x_phys = self.pipeline.physical_density(self.x)
        self.change  = float(np.max(np.abs(self.x - old)))

    # ── Reporting ─────────────────────────────────────────────────────────────
    # The engine owns the loop counter and the stopping decision; this method
    # only reports what happened.  See core/contract.py.

    def get_density(self):   return self.x_phys
    def get_change(self):    return self.change

    def get_responses(self):
        return {
            OBJECTIVE: self.objective,
            "volume": float(self.x_phys.mean()),
        }

