# methods/density_mma.py - SIMP density topology optimisation with MMA updates
#
# This method mirrors the optimizer part of the supplied top88mma.m script:
# FEA and raw SIMP sensitivities are computed here, filters are delegated to
# DensityFilterPipeline, and the design update is performed by an MMA
# moving-asymptote subproblem with one normalized volume constraint.

import numpy as np

from toporia.core.contract import OBJECTIVE, Capabilities, OptimizationMethod
from toporia.core.params import Param
from toporia.library.fe.q4_plane_stress import solve_fea

from ._shared_params import MOVE, PENAL
from .filter_chain import DensityFilterPipeline


class DensityMMAMethod(OptimizationMethod):

    name = "density_mma"
    label = "SIMP density (MMA)"
    aliases = ("mma",)
    order = 20
    params = (
        PENAL,
        MOVE,
        Param("mma_tol", 1e-4, "MMA tolerance",
              "MMA's own, stricter convergence test on the largest design change. "
              "The engine's tolerance still applies as well.",
              min=0.0, max=1.0, step=1e-4, decimals=6),
        Param("asyinit", 0.5, "Asymptote init", "Initial asymptote distance, as a fraction of the bounds.",
              min=0.01, max=1.0, step=0.05, decimals=2),
        Param("asyincr", 1.2, "Asymptote grow", "Asymptote expansion after consistent design motion.",
              min=1.0, max=2.0, step=0.05, decimals=2),
        Param("asydecr", 0.7, "Asymptote shrink", "Asymptote contraction after oscillating design motion.",
              min=0.1, max=1.0, step=0.05, decimals=2),
        Param("c", 1000.0, "Constraint scale", "Penalty scale on the volume constraint in the MMA subproblem.",
              min=1.0, max=1e6, step=100.0, decimals=0),
    )
    capabilities = Capabilities(variable_kind="density", accepts_filters=True)

    def initialize(self, problem, solver):
        self.problem = problem
        self.solver = solver
        self.settings = self.resolve_params(solver)   # this method's Param values
        self.iteration = 0
        self.objective = np.inf
        self.change = np.inf

        n_total   = problem.nelx * problem.nely
        n_passive = int(np.sum(problem.passive_elements))
        if n_passive > problem.scenario.volfrac * n_total:
            raise ValueError(
                f"Infeasible volume fraction: passive (forced-solid) elements already "
                f"fill {n_passive / n_total:.1%} of the domain, which exceeds "
                f"volfrac={problem.scenario.volfrac:.1%}. Raise volfrac or reduce the passive region."
            )

        # Per-element bounds replace the passive/void masks (see density_top88).
        self.lb, self.ub = problem.lower_bound, problem.upper_bound
        self.x = np.clip(np.full((problem.nely, problem.nelx), problem.scenario.volfrac), self.lb, self.ub)

        self.pipeline = DensityFilterPipeline(problem, solver)
        self.x_phys = self.pipeline.physical_density(self.x)

        self.n = problem.nelx * problem.nely
        self.xmin = np.zeros(self.n)
        self.xmax = np.ones(self.n)
        self.low = self.xmin.copy()
        self.upp = self.xmax.copy()
        self.xold1 = self.x.reshape(-1, order="F").copy()
        self.xold2 = self.xold1.copy()

        self.asyinit = self.settings["asyinit"]
        self.asyincr = self.settings["asyincr"]
        self.asydecr = self.settings["asydecr"]
        self.c_mma = self.settings["c"]
        self.convtol = self.settings["mma_tol"]
        self.f0fac = None

    def step(self, iteration):
        problem = self.problem
        sc = problem.scenario   # material and volume target
        # Completed-iteration count: MMA's warm-up tests and the filter continuation
        # schedules were both written against a zero-based counter.
        self.iteration = iteration - 1

        penal = self.settings["penal"]
        _, ce, self.objective = solve_fea(problem, self.x_phys, penal)

        dc = -penal * (sc.E0 - sc.Emin) * self.x_phys ** (penal - 1.0) * ce
        solid_limit = max(sc.volfrac * float(problem.nelx * problem.nely), 1e-12)
        volume = float(np.sum(self.x_phys) / solid_limit)
        dv = np.ones_like(self.x_phys) / solid_limit

        dc, dv = self.pipeline.sensitivities(dc, dv)
        self.pipeline.step(self.iteration)

        if self.f0fac is None:
            self.f0fac = 10.0 / max(abs(self.objective), 1e-12)
        elif self.iteration >= 19 and self.f0fac * self.objective < 0.1:
            self.f0fac = 1.0 / max(abs(self.objective), 1e-12)

        xval = self.x.reshape(-1, order="F")
        df0dx = dc.reshape(-1, order="F") * self.f0fac
        fval = volume - 1.0
        dfdx = dv.reshape(-1, order="F")

        xmma, self.low, self.upp = self._mma_update(xval, df0dx, fval, dfdx)
        xnew = xmma.reshape(problem.nely, problem.nelx, order="F")
        xnew = np.clip(xnew, self.lb, self.ub)

        old = self.x.copy()
        self.xold2 = self.xold1
        self.xold1 = xval.copy()
        self.x = np.clip(xnew, 0.0, 1.0)
        self.x_phys = self.pipeline.physical_density(self.x)
        self.change = float(np.max(np.abs(self.x - old)))

    def _mma_update(self, xval, df0dx, fval, dfdx):
        """Solve the one-constraint MMA approximation used for volume control."""
        n = self.n
        xmin, xmax = self.xmin, self.xmax
        xmamieps = 1e-5

        if self.iteration < 2:
            low = xval - self.asyinit * (xmax - xmin)
            upp = xval + self.asyinit * (xmax - xmin)
        else:
            zzz = (xval - self.xold1) * (self.xold1 - self.xold2)
            factor = np.ones(n)
            factor[zzz > 0.0] = self.asyincr
            factor[zzz < 0.0] = self.asydecr
            low = xval - factor * (self.xold1 - self.low)
            upp = xval + factor * (self.upp - self.xold1)
            low = np.maximum(low, xval - 10.0 * (xmax - xmin))
            low = np.minimum(low, xval - 0.01 * (xmax - xmin))
            upp = np.minimum(upp, xval + 10.0 * (xmax - xmin))
            upp = np.maximum(upp, xval + 0.01 * (xmax - xmin))

        alpha = np.maximum(xmin, low + 0.1 * (xval - low))
        beta = np.minimum(xmax, upp - 0.1 * (upp - xval))
        alpha = np.maximum(alpha, xval - self.settings["move"])
        beta = np.minimum(beta, xval + self.settings["move"])

        ux1 = upp - xval
        xl1 = xval - low
        ux2 = ux1 * ux1
        xl2 = xl1 * xl1
        xmami = np.maximum(xmax - xmin, xmamieps)
        regularizer = 1e-5 * np.maximum(np.abs(df0dx), 1.0 / xmami)

        p0 = np.maximum(df0dx, 0.0) + regularizer
        q0 = np.maximum(-df0dx, 0.0) + regularizer
        p0 *= ux2
        q0 *= xl2

        p = np.maximum(dfdx, 0.0) + 1e-5 * np.maximum(np.abs(dfdx), 1.0 / xmami)
        q = np.maximum(-dfdx, 0.0) + 1e-5 * np.maximum(np.abs(dfdx), 1.0 / xmami)
        p *= ux2
        q *= xl2
        b = float(np.sum(p / ux1 + q / xl1) - fval)

        def candidate(lam):
            plam = p0 + lam * p
            qlam = q0 + lam * q
            sqrtp = np.sqrt(np.maximum(plam, 0.0))
            sqrtq = np.sqrt(np.maximum(qlam, 0.0))
            x = (sqrtp * low + sqrtq * upp) / (sqrtp + sqrtq + 1e-30)
            return np.minimum(beta, np.maximum(alpha, x))

        def constraint_at(x):
            return float(np.sum(p / (upp - x) + q / (x - low)) - b)

        x0 = candidate(0.0)
        if constraint_at(x0) <= 0.0:
            return x0, low, upp

        lam_low, lam_high = 0.0, 1.0
        while constraint_at(candidate(lam_high)) > 0.0 and lam_high < self.c_mma:
            lam_low = lam_high
            lam_high *= 2.0
        lam_high = min(lam_high, self.c_mma)

        for _ in range(80):
            lam = 0.5 * (lam_low + lam_high)
            x = candidate(lam)
            if constraint_at(x) > 0.0:
                lam_low = lam
            else:
                lam_high = lam
            if lam_high - lam_low < 1e-10 * (1.0 + lam_high):
                break

        return candidate(lam_high), low, upp

    def is_converged(self):
        """MMA uses a tighter tolerance than the platform default (method.mma_tol).

        The engine's own `change < solver.tol` rule still applies and still wins
        if it triggers first; this only adds MMA's stricter criterion.
        """
        return self.change < self.convtol

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

