"""Independent cell-centred variant of Otomori et al.'s reaction-diffusion method.

Positive phi is solid. Backward Euler evolves phi_t = T/<|T|> - lambda
+ ell^2 Laplacian(phi), with no-flux outer boundaries and phi in [-1, 1].
T is the elastic topological benefit (2015 paper, Appendix C), extended into
ersatz material by its local modulus. It is not the SIMP density gradient.
The scalar multiplier is bisected on the *updated* smoothed-Heaviside volume.
This replaces the reference's augmented-Lagrangian volume feedback. There is
no Dirac band, signed-distance reinitialisation, dense RBF or mesh coarsening.

The cell-centred discretisation, cubic Heaviside and multiplier solve are
Toporia choices, not a port or a bit-for-bit reproduction of levelset88.m.
The tensor is the paper's plane-stress reduction of its spherical-cavity
tensor; it is not claimed to be the circular-hole asymptotic tensor.
"""

import numpy as np
from scipy.sparse import eye, kron
from scipy.sparse.linalg import splu

from toporia.framework.params import Param
from toporia.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod
from toporia.plugins.filters.pde_anisotropic import _neumann_laplacian
from toporia.plugins.interpolations.simp import SIMP
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress, element_stiffness


def topological_matrix(nu, dx, dy):
    """Integral B.T A B for unit E, using Appendix C's in-plane tensor.

Its engineering-strain matrix has diagonals A1+2*A2, A1+2*A2, A2
and normal coupling A1. Reusing Q4 quadrature with c=A1/(A1+2*A2)
is algebraically exact, including nonsquare elements.
"""
    if not np.isfinite(nu) or not -1 < nu < 0.5:
        raise ValueError("The topological tensor requires -1 < Poisson's ratio < 0.5")
    factor = 3 * (1 - nu) / (2 * (1 + nu) * (7 - 5 * nu))
    a1 = -factor * (1 - 14 * nu + 15 * nu**2) / (1 - 2 * nu)**2
    a2 = 5 * factor
    c = a1 / (a1 + 2 * a2)
    return element_stiffness(c, dx, dy) * (a1 + 2 * a2) * (1 - c*c)


def material_fraction(phi, width):
    """C1 cubic Heaviside, exactly void/solid outside [-width, width]."""
    t = np.clip(np.asarray(phi) / width, -1.0, 1.0)
    return 0.5 + 0.75*t - 0.25*t**3


class ReactionDiffusionLevelSet(OptimizationMethod):
    name = "levelset_reaction_diffusion"
    label = "Reaction-diffusion level set"
    reference = (
        'M. Otomori, T. Yamada, K. Izui and S. Nishiwaki, "Matlab code for a '
        'level set-based topology optimization method using a reaction diffusion '
        'equation", SMO 51 (2015) 1159-1172. Independent cell-centred variant '
        'with implicit diffusion and a bisected volume multiplier; no original code copied.'
        ' Papers: https://doi.org/10.1007/s00158-014-1190-z'
    )
    order = 31
    capabilities = Capabilities(variable_kind="level_set")
    params = (
        Param("dt", 0.1, "Time step", "Pseudo-time step of the bounded level-set evolution.",
              min=0.001, max=1.0, decimals=3),
        Param("diffusion_length", 1.0, "Diffusion length",
              "Square root of the diffusion coefficient, in physical mm. Larger values smooth more.",
              min=0.0, max=100.0, decimals=3, units="mm"),
        Param("interface_width", 0.1, "Heaviside half-width",
              "Dimensionless phi band for mixed cells; outside it material is exactly solid or void.",
              min=0.001, max=1.0, decimals=3),
        Param("nrelax", 30, "Volume ramp iterations",
              "Ramp from the initial solid volume to the budget. Zero enforces the budget immediately.",
              min=0, max=500),
    )

    def initialize(self, problem, solver):
        reasons = self.capabilities.problems_with(problem.scenario)
        if len(problem.shape) != 2:
            reasons.append("reaction-diffusion level set supports only 2-D")
        if reasons:
            raise ValueError("; ".join(reasons))
        self.settings = self.resolve_params(solver)
        self.problem = problem
        self.iteration = 0
        self.change = np.inf
        self.dt = self.settings["dt"]
        self.width = self.settings["interface_width"]
        self.nrelax = self.settings["nrelax"]
        requested_volume = float(problem.scenario.volfrac)
        self.lower = problem.lower_bound.ravel()
        self.upper = problem.upper_bound.ravel()
        if self.lower.mean() > requested_volume:
            raise ValueError("Volume budget is unreachable with the fixed solid/void regions")
        # It is an upper budget: forced void may leave less material available.
        self.target = min(requested_volume, float(self.upper.mean()))
        self.fixed = self.lower == self.upper
        self.free = ~self.fixed
        self.phi = np.ones(problem.shape)
        self.phi.ravel()[self.fixed] = 2*self.lower[self.fixed] - 1
        self.density = self._density(self.phi.ravel()).reshape(problem.shape)
        self.initial_volume = float(self.density.mean())
        self.volume_target = self.initial_volume
        self.multiplier = 0.0
        ny, nx = problem.shape
        laplacian = (kron(eye(ny), _neumann_laplacian(nx)) / problem.dx**2
                     + kron(_neumann_laplacian(ny), eye(nx)) / problem.dy**2)
        self.operator = (eye(nx*ny) + self.dt*self.settings["diffusion_length"]**2*laplacian).tocsc()
        if self.free.any():
            self.lu = splu(self.operator[self.free][:, self.free].tocsc())
            self.fixed_rhs = self.operator[self.free][:, self.fixed] @ self.phi.ravel()[self.fixed]
            self.multiplier_direction = self.dt*self.lu.solve(np.ones(self.free.sum()))
        self.physics = Q4PlaneStress()
        self.physics.initialize(problem, {}, SIMP(penal=1.0))
        self.td_matrix = topological_matrix(problem.scenario.nu, problem.dx, problem.dy)
        self.state = self.physics.solve(self.density)

    def _density(self, phi):
        return np.clip(material_fraction(phi, self.width), self.lower, self.upper)

    def topological_benefit(self):
        """Weighted load-case contraction, per unit physical cell area."""
        state = self.state
        energy = np.zeros(self.problem.nelx*self.problem.nely)
        for case, weight in enumerate(state.weights):
            displacement = state.U[self.physics.edof, case]
            energy += weight*np.einsum("ei,ij,ej->e", displacement, self.td_matrix, displacement)
        field = (state.stiffness*energy).reshape(self.problem.shape, order="F")
        return field / (self.problem.dx*self.problem.dy)

    def _evolve(self, benefit, target):
        """One implicit diffusion step; bisection requires no additional FE solves."""
        previous = self.phi.ravel()
        if not self.free.any():
            return previous.copy(), 0.0
        forcing = benefit.ravel()[self.free]
        scale = max(float(np.mean(np.abs(forcing))), np.finfo(float).tiny)
        trial = self.lu.solve(previous[self.free] + self.dt*forcing/scale - self.fixed_rhs)
        direction = self.multiplier_direction

        def candidate(multiplier):
            phi = previous.copy()
            phi[self.free] = np.clip(trial - multiplier*direction, -1.0, 1.0)
            return phi

        # Bounds put every free cell outside the Heaviside transition. The
        # inverse of this M-matrix is positive, so volume decreases with lambda.
        lo = float(np.min((trial - 1.0) / direction)) - 1.0
        hi = float(np.max((trial + 1.0) / direction)) + 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            if self._density(candidate(mid)).mean() > target:
                lo = mid
            else:
                hi = mid
        # The upper bracket is always feasible, including at volume endpoints.
        return candidate(hi), hi

    def step(self, iteration):
        self.iteration = iteration
        progress = min(iteration / self.nrelax, 1.0) if self.nrelax else 1.0
        self.volume_target = self.initial_volume + progress*(self.target - self.initial_volume)
        old_phi = self.phi.copy()
        phi, self.multiplier = self._evolve(self.topological_benefit(), self.volume_target)
        self.phi = phi.reshape(self.problem.shape)
        self.density = self._density(phi).reshape(self.problem.shape)
        self.change = float(np.max(np.abs(self.phi - old_phi)))
        # Report the objective of the same design that is exported and plotted.
        self.state = self.physics.solve(self.density)

    def continuing(self):
        return self.iteration < self.nrelax

    def get_density(self):
        return self.density

    def get_change(self):
        return self.change

    def get_responses(self):
        return {OBJECTIVE: float(np.dot(self.state.weights, self.state.compliances)),
                "volume": float(self.density.mean()), "volume_target": self.volume_target,
                "volume_multiplier": self.multiplier}
