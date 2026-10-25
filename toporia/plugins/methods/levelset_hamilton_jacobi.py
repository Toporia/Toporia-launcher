"""Independent 2-D HJ/TD variant after Challis (2010), not a MATLAB code port.

phi is positive in solid, reversing Challis's sign convention. The evolution
phi_t = (W-lambda)|grad(phi)| + omega*(T-lambda)*initial_solid combines shape
motion with circular-hole topological forcing. The augmented-Lagrangian
volume feedback, cross-shaped sensitivity smoothing and CFL evolution follow
the paper. Toporia normalises cell energies by their initial mean for material
and load-unit invariance, protects support/force cells, and requires feasibility
for its joint volume/objective stopping criterion. No original code is copied.
"""

import numpy as np
from scipy.ndimage import convolve, distance_transform_edt

from toporia.framework.params import Param
from toporia.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod
from toporia.plugins.interpolations.simp import SIMP
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress, element_stiffness


def circular_hole_matrix(nu, dx, dy):
    """Integrated unit-E plane-stress cavity derivative per removed area.

For solid stress sigma, T = (4 sigma:sigma - trace(sigma)^2)/E.
This is Challis Eq. 13 divided by pi, using the plane-stress Lame
coefficient. Engineering-stress ordering is (xx, yy, xy); the shear term
has coefficient eight. Its strain matrix has entries a, b, (a-b)/2.
"""
    if not np.isfinite(nu) or not -1 < nu < 0.5:
        raise ValueError("Circular-hole sensitivity requires -1 < Poisson's ratio < 0.5")
    a = (3 + 3*nu**2 - 2*nu) / (1-nu**2)**2
    b = (-1 - nu**2 + 6*nu) / (1-nu**2)**2
    c = b/a
    return a*(1-c*c)*element_stiffness(c, dx, dy)


def signed_distance(solid, dx, dy):
    """Cell-centred EDT with exterior void; positive inside material, in mm.

The half-minimum-cell offset approximates an interface between opposite cells.
It is exact for an axis-aligned interface on square cells, not a subcell cut FE.
"""
    solid = np.asarray(solid, dtype=bool)
    h = min(dx, dy)
    if not solid.any():
        return np.full(solid.shape, -np.hypot(dx*solid.shape[1], dy*solid.shape[0]))
    padded = np.pad(solid, 1, constant_values=False)
    inside = distance_transform_edt(padded, sampling=(dy, dx))[1:-1, 1:-1]
    outside = distance_transform_edt(~padded, sampling=(dy, dx))[1:-1, 1:-1]
    return np.where(solid, inside-0.5*h, -outside+0.5*h)


def godunov_norm(phi, velocity, dx, dy):
    """Upwind |grad phi| for phi_t = velocity*|grad phi| (positive inside).

Velocity is the negative of F in the usual phi_t + F |grad phi| = 0.
The exterior is void and does not wrap around the rectangular domain.
"""
    padded = np.pad(phi, 1, constant_values=-0.5*min(dx, dy))
    backward_x = (phi-padded[1:-1, :-2])/dx
    forward_x = (padded[1:-1, 2:]-phi)/dx
    backward_y = (phi-padded[:-2, 1:-1])/dy
    forward_y = (padded[2:, 1:-1]-phi)/dy
    growing = (np.maximum(np.minimum(backward_x, 0)**2, np.maximum(forward_x, 0)**2)
               + np.maximum(np.minimum(backward_y, 0)**2, np.maximum(forward_y, 0)**2))
    shrinking = (np.maximum(np.maximum(backward_x, 0)**2, np.minimum(forward_x, 0)**2)
                 + np.maximum(np.maximum(backward_y, 0)**2, np.minimum(forward_y, 0)**2))
    return np.sqrt(np.where(velocity >= 0, growing, shrinking))


class HamiltonJacobiLevelSet(OptimizationMethod):
    name = "levelset_hamilton_jacobi"
    label = "Hamilton-Jacobi level set (circular TD)"
    reference = (
        'V. J. Challis, "A discrete level-set topology optimization code written in '
        'Matlab", SMO 41 (2010) 453-464. Independent positive-inside, physically '
        'scaled HJ/TD variant with normalised augmented-Lagrangian feedback; no original code copied.'
        ' Papers: https://doi.org/10.1007/s00158-009-0430-0'
    )
    order = 32
    capabilities = Capabilities(variable_kind="level_set")
    params = (
        Param("step_length", 3.0, "Evolution interval",
              "Pseudo-time interval per update in minimum cell widths; internally CFL-subcycled.",
              min=0.1, max=5.0, decimals=2),
        Param("topological_weight", 2.0, "Hole forcing weight",
              "Weight of circular-hole forcing in initially solid cells; zero gives pure HJ advection.",
              min=0.0, max=5.0, decimals=2),
        Param("reinitialise_every", 2, "Reinitialise every",
              "Updates between signed-distance resets; zero disables resets. Frequent resets inhibit nucleation.",
              min=0, max=100),
        Param("multiplier_initial", -0.01, "Initial volume multiplier",
              "Initial augmented-Lagrangian multiplier in normalised cell-energy units.",
              min=-10.0, max=10.0, decimals=4),
        Param("penalty_initial", 1000.0, "Initial penalty denominator",
              "Denominator of volume feedback; smaller values enforce volume more aggressively.",
              min=0.001, max=1e6, decimals=3),
        Param("penalty_decay", 0.9, "Penalty denominator decay",
              "Factor per update, bounded below at 1e-6 to avoid division by zero on long runs.",
              min=0.5, max=1.0, decimals=3),
        Param("volume_tolerance", 0.005, "Volume settling tolerance",
              "Joint stopping criterion: fraction below the budget; overspending never counts as settled.",
              min=0.0, max=0.1, decimals=4),
        Param("objective_tolerance", 0.01, "Objective settling tolerance",
              "Relative tolerance against five previous objectives, once volume is feasible and settled.",
              min=0.0, max=0.1, decimals=4),
    )

    def initialize(self, problem, solver):
        reasons = self.capabilities.problems_with(problem.scenario)
        if len(problem.shape) != 2:
            reasons.append("Hamilton-Jacobi level set supports only 2-D")
        if reasons:
            raise ValueError("; ".join(reasons))
        self.settings = self.resolve_params(solver)
        self.problem = problem
        self.iteration = 0
        self.h = min(problem.dx, problem.dy)
        self.physics = Q4PlaneStress()
        self.physics.initialize(problem, {}, SIMP(penal=1.0))
        self.td_matrix = circular_hole_matrix(problem.scenario.nu, problem.dx, problem.dy)
        self.solid = problem.passive_elements.copy()
        # Keep cells touching an applied force solid, as in the reference.
        for _, force in self.physics.layout.forces:
            loaded = np.any(force[self.physics.edof] != 0, axis=1)
            self.solid |= loaded.reshape(problem.shape, order="F")
        self.void = problem.void_elements.copy()
        if np.any(self.solid & self.void):
            raise ValueError("A force-bearing cell overlaps an enforced void region")
        supported = np.any(np.isin(self.physics.edof, self.physics.layout.fixed_dofs), axis=1)
        self.solid |= supported.reshape(problem.shape, order="F") & ~self.void
        self.fixed = self.solid | self.void
        count = int(np.prod(problem.shape))
        self.target_cells = min(int(np.floor(problem.scenario.volfrac*count + 1e-12)),
                                count-int(self.void.sum()))
        if int(self.solid.sum()) > self.target_cells:
            raise ValueError("Volume budget is below the mandatory solid/force-bearing cells")
        self.density = (~self.void).astype(float)
        self.phi = signed_distance(self.density > 0, problem.dx, problem.dy)
        self._pin(self.phi)
        self.initial_cells = int(self.density.sum())
        self.volume_target = self.target_cells/count
        self.lag = self.settings["multiplier_initial"]
        self.penalty = self.settings["penalty_initial"]
        self.multiplier = self.lag
        self.change = np.inf
        self.state = self.physics.solve(self.density)
        initial_objective = float(np.dot(self.state.weights, self.state.compliances))
        self.energy_scale = max(initial_objective/count, np.finfo(float).tiny)
        self.objective_history = []

    def _pin(self, phi):
        phi[self.solid] = np.maximum(phi[self.solid], 0.5*self.h)
        phi[self.void] = np.minimum(phi[self.void], -0.5*self.h)

    def sensitivities(self):
        """Weighted shape benefit and true solid circular-hole derivative per area.

The local modulus extends both fields to ersatz cells for velocity smoothing;
topological forcing itself is applied only in initially solid cells.
"""
        state = self.state
        shape = sum(w*ce for w, ce in zip(state.weights, state.energies, strict=True))
        topological = np.zeros(self.problem.nelx*self.problem.nely)
        for case, weight in enumerate(state.weights):
            u = state.U[self.physics.edof, case]
            topological += weight*np.einsum("ei,ij,ej->e", u, self.td_matrix, u)
        modulus = state.stiffness.reshape(self.problem.shape, order="F")
        area = self.problem.dx*self.problem.dy
        return (modulus*shape/area,
                modulus*topological.reshape(self.problem.shape, order="F")/area)

    def _evolve(self, velocity, forcing):
        p = self.problem
        v = np.where(self.fixed, 0.0, velocity)
        q = np.where((self.phi > 0) & ~self.fixed, forcing, 0.0)
        weight = self.settings["topological_weight"]
        scale = float(np.max(np.abs(v)))
        if scale == 0.0:
            # There is no advective CFL time when v vanishes. Evolve the
            # frozen source on its own finite scale (or do nothing if q=0).
            scale = max(float(np.max(np.abs(q)))*max(weight, 1.0), 1.0)
        v, q = v/scale, q/scale
        # Max |v| <= 1; dt*(1/dx+1/dy) <= 0.2. Reaction is frozen over
        # this update (including its initial-solid mask), as in Challis.
        steps = max(1, int(np.ceil(10*self.settings["step_length"])))
        dt = self.settings["step_length"]*self.h/steps
        phi = self.phi.copy()
        for _ in range(steps):
            phi += dt*(v*godunov_norm(phi, v, p.dx, p.dy) + weight*q)
            self._pin(phi)
        return phi

    def step(self, iteration):
        self.iteration = iteration
        shape, topological = self.sensitivities()
        area = self.problem.dx*self.problem.dy
        shape, topological = shape*area/self.energy_scale, topological*area/self.energy_scale
        error = float(self.density.mean())-self.volume_target
        self.multiplier = self.lag+error/self.penalty
        kernel = np.array([[0, 1, 0], [1, 2, 1], [0, 1, 0]], dtype=float)/6
        velocity = convolve(shape-self.multiplier, kernel, mode="nearest")
        # Challis uses a unit-ball perturbation: both compliance and volume
        # cavity derivatives have a factor pi. It belongs in the source term.
        forcing = np.pi*convolve(topological-self.multiplier, kernel, mode="nearest")
        old_phi = self.phi.copy()
        self.phi = self._evolve(velocity, forcing)
        self.density = (self.phi > 0).astype(float)
        reinitialise = self.settings["reinitialise_every"]
        if reinitialise and iteration % reinitialise == 0:
            self.phi = signed_distance(self.density > 0, self.problem.dx, self.problem.dy)
            self._pin(self.phi)
        self.change = float(np.max(np.abs(self.phi-old_phi)))/self.h
        self.state = self.physics.solve(self.density)
        self.objective_history.append(float(np.dot(self.state.weights, self.state.compliances)))
        self.lag += error/self.penalty
        self.penalty = max(self.penalty*self.settings["penalty_decay"], 1e-6)

    def continuing(self):
        error = float(self.density.mean())-self.volume_target
        return self.iteration < 6 or error > 1e-12 or error < -self.settings["volume_tolerance"]

    def is_converged(self):
        if self.continuing() or len(self.objective_history) < 6:
            return False
        current = self.objective_history[-1]
        return all(abs(current-value)/max(abs(current), 1.0) < self.settings["objective_tolerance"]
                   for value in self.objective_history[-6:-1])

    def convergence_reason(self):
        return "feasible volume settled and compliance stable against five previous iterations"

    def get_density(self):
        return self.density

    def get_change(self):
        return self.change

    def get_responses(self):
        return {OBJECTIVE: float(np.dot(self.state.weights, self.state.compliances)),
                "volume": float(self.density.mean()), "volume_target": self.volume_target,
                "volume_multiplier": self.multiplier, "penalty_denominator": self.penalty}
