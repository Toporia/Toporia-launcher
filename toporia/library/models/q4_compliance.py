# library/models/q4_compliance.py — compliance on Toporia's own 2-D Q4 solver.
#
# Design variable: x[i, j] ∈ [0, 1], the density of element (i, j) before
# filtering.  The filter pipeline turns it into the physical density, SIMP
# turns that into stiffness, and the Q4 solver gives the compliance:
#
#     x ──filters──> x_phys ──SIMP: E = Emin + x_phys^p (E0 − Emin)──> K ──solve──> C
#
# Gradients come back the same way: the raw SIMP sensitivity with respect to
# the physical density, then the filter pipeline's adjoint to the design.
#
# This is the physics half of the top88 code by Andreassen et al. (2011); the
# update half (OC or MMA) lives in library/updaters.

import numpy as np

from toporia.core.composition import Evaluation, Model
from toporia.core.contract import Capabilities
from toporia.library.fe.q4_plane_stress import solve_fea
from toporia.library.filters.pipeline import DensityFilterPipeline

from ._common import PENAL


class Q4ComplianceModel(Model):
    """Weighted compliance of a SIMP density design on the 2-D Q4 plane-stress solver."""

    name = "q4_compliance"
    label = "Compliance, 2-D Q4 (Toporia)"
    order = 10
    params = (PENAL,)
    capabilities = Capabilities(variable_kind="density", accepts_filters=True)

    def initialize(self, problem, solver, settings):
        self.problem = problem
        self.penal = settings["penal"]
        scenario = problem.scenario

        n_total = problem.nelx * problem.nely
        n_passive = int(np.sum(problem.passive_elements))
        if n_passive > scenario.volfrac * n_total:
            raise ValueError(
                f"Infeasible volume fraction: passive (forced-solid) elements already "
                f"fill {n_passive / n_total:.1%} of the domain, which exceeds "
                f"volfrac={scenario.volfrac:.1%}. Raise volfrac or reduce the passive region."
            )

        self.lb, self.ub = problem.lower_bound, problem.upper_bound
        self.volume_limit = scenario.volfrac * n_total
        self.pipeline = DensityFilterPipeline(problem, solver)

    def initial_design(self):
        problem = self.problem
        full = np.full((problem.nely, problem.nelx), problem.scenario.volfrac)
        return np.clip(full, self.lb, self.ub)

    def bounds(self):
        return self.lb, self.ub

    def physical(self, x):
        return self.pipeline.physical_density(x)

    def evaluate(self, x):
        scenario = self.problem.scenario
        x_phys = self.physical(x)
        _, ce, compliance = solve_fea(self.problem, x_phys, self.penal)

        # Raw sensitivities with respect to the physical density ...
        dc = -self.penal * (scenario.E0 - scenario.Emin) * x_phys ** (self.penal - 1.0) * ce
        dv = np.ones_like(x)
        # ... mapped back to the design through the filter pipeline's adjoint.
        dc, dv = self.pipeline.sensitivities(dc, dv)
        return Evaluation(objective=compliance, objective_gradient=dc,
                          volume=np.sum(x_phys), volume_gradient=dv)

    def advance(self, completed):
        self.pipeline.step(completed)
