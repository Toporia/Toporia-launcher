# methods/density_mma.py - SIMP density topology optimisation with MMA updates
#
# This method mirrors the optimizer part of the supplied top88mma.m script:
# FEA and raw SIMP sensitivities are computed here, filters are delegated to
# DensityFilterPipeline, and the design update is performed by an MMA
# moving-asymptote subproblem with one normalized volume constraint.

import numpy as np

from .base import OptimizationMethod, solve_fea
from .filter_chain import DensityFilterPipeline


class DensityMMAMethod(OptimizationMethod):

    def initialize(self, problem, config):
        self.problem = problem
        self.config = config
        self.iteration = 0
        self.objective = np.inf
        self.change = np.inf

        n_total   = problem.nelx * problem.nely
        n_passive = int(np.sum(problem.passive_elements))
        if n_passive > config.volfrac * n_total:
            raise ValueError(
                f"Infeasible volume fraction: passive (forced-solid) elements already "
                f"fill {n_passive / n_total:.1%} of the domain, which exceeds "
                f"volfrac={config.volfrac:.1%}. Raise volfrac or reduce the passive region."
            )

        self.x = np.full((problem.nely, problem.nelx), config.volfrac)
        self.x[problem.passive_elements] = 1.0
        self.x[problem.void_elements] = 0.0

        self.pipeline = DensityFilterPipeline(problem, config)
        self.x_phys = self.pipeline.physical_density(self.x)

        self.n = problem.nelx * problem.nely
        self.xmin = np.zeros(self.n)
        self.xmax = np.ones(self.n)
        self.low = self.xmin.copy()
        self.upp = self.xmax.copy()
        self.xold1 = self.x.reshape(-1, order="F").copy()
        self.xold2 = self.xold1.copy()

        self.asyinit = float(getattr(config, "mma_asyinit", 0.5))
        self.asyincr = float(getattr(config, "mma_asyincr", 1.2))
        self.asydecr = float(getattr(config, "mma_asydecr", 0.7))
        self.c_mma = float(getattr(config, "mma_c", 1000.0))
        self.convtol = float(getattr(config, "mma_tol", min(config.tol, 1e-4)))
        self.f0fac = None

    def step(self):
        cfg, problem = self.config, self.problem

        _, ce, self.objective = solve_fea(problem, cfg, self.x_phys)

        dc = -cfg.penal * (cfg.E0 - cfg.Emin) * self.x_phys ** (cfg.penal - 1.0) * ce
        solid_limit = max(cfg.volfrac * float(problem.nelx * problem.nely), 1e-12)
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
        xnew[problem.passive_elements] = 1.0
        xnew[problem.void_elements] = 0.0

        old = self.x.copy()
        self.xold2 = self.xold1
        self.xold1 = xval.copy()
        self.x = np.clip(xnew, 0.0, 1.0)
        self.x_phys = self.pipeline.physical_density(self.x)
        self.change = float(np.max(np.abs(self.x - old)))
        self.iteration += 1

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
        alpha = np.maximum(alpha, xval - self.config.move)
        beta = np.minimum(beta, xval + self.config.move)

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

    def has_converged(self):
        return self.iteration >= self.config.max_iter or self.change < self.convtol

    def get_density(self): return self.x_phys
    def get_objective(self): return self.objective
    def get_iteration(self): return self.iteration
