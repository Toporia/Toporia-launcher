"""Linear Q4 elasticity with fixed port springs and signed point probes.

Own implementation for compliant mechanisms (Sigmund 1997). The base Q4
solver is unchanged. Springs add a density-independent diagonal to K, and
the SAME augmented K is used by the real loads and every adjoint. External
work includes spring energy; material sensitivities only differentiate the
element contribution. One sparse LU is shared by all load cases and adjoints.
Papers: https://doi.org/10.1080/08905459708945415
"""

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import splu

from toporia.framework.parts.physics import POINT_DISPLACEMENT, PointDisplacementPhysics
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress, Q4Solution


class Q4Mechanism(Q4PlaneStress, PointDisplacementPhysics):
    name = "q4_mechanism"
    label = "2-D Q4 elasticity with port springs"
    order = 13
    provides = (*Q4PlaneStress.provides, POINT_DISPLACEMENT)
    supports_springs = True

    def initialize(self, problem, settings, interpolation=None):
        super().initialize(problem, settings, interpolation)
        self.spring_diagonal = np.zeros(self.layout.ndof)
        for spring in problem.scenario.point_springs:
            node = self._node(spring.x, spring.y)
            self.spring_diagonal[2 * node + (spring.dof == "y")] += spring.stiffness
        # Springs are supports in their own right: do not invent a clamp when
        # they are the only supports, but reject incomplete rigid-body restraint.
        rigid = np.zeros((self.layout.ndof, 3))
        rigid[0::2, 0], rigid[1::2, 1] = 1.0, 1.0
        length = max(problem.Lx, problem.Ly)
        rigid[0::2, 2] = -problem.node_y.ravel(order="F") / length
        rigid[1::2, 2] = problem.node_x.ravel(order="F") / length
        restrained = np.union1d(self.layout.fixed_dofs, np.flatnonzero(self.spring_diagonal > 0))
        if restrained.size == 0 or np.linalg.matrix_rank(rigid[restrained]) < 3:
            raise ValueError("supports and positive point springs leave rigid-body motion unconstrained")
        self._rows = np.tile(self.edof, (1, 8)).ravel()
        self._cols = np.repeat(self.edof, 8, axis=1).ravel()

    def _node(self, x, y):
        p = self.problem
        if not np.all(np.isfinite([x, y])) or not (0 <= x <= p.Lx and 0 <= y <= p.Ly):
            raise ValueError("spring/probe coordinates must be finite and inside the design domain")
        ix = int(np.argmin(np.abs(np.arange(p.nelx + 1) * p.dx - x)))
        iy = int(np.argmin(np.abs(np.arange(p.nely + 1) * p.dy - y)))
        return int(self.layout.node_ids[iy, ix])

    def solve(self, density):
        scenario, layout = self.problem.scenario, self.layout
        stiffness = self.material.stiffness(density.reshape(-1, order="F"), scenario.E0, scenario.Emin)
        values = (self.KE.ravel(order="F")[None, :] * stiffness[:, None]).ravel()
        K = coo_matrix((values, (self._rows, self._cols)), shape=(layout.ndof, layout.ndof)).tocsc()
        K = (K + K.T) * 0.5 + diags(self.spring_diagonal, format="csc")
        free = layout.free_dofs
        Kff = K[free][:, free].tocsc()
        factor = splu(Kff)
        U = np.zeros((layout.ndof, len(layout.forces)))
        energies, compliances = [], []
        for case, (_, force) in enumerate(layout.forces):
            U[free, case] = factor.solve(force[free])
            displacement = U[self.edof, case]
            energies.append(self._field(np.sum((displacement @ self.KE) * displacement, axis=1)))
            # f^T u includes both material and fixed-spring elastic energy.
            compliances.append(float(force @ U[:, case]))
        state = Q4Solution(density, stiffness, U, Kff, [w for w, _ in layout.forces], energies, compliances)
        state.factor = factor
        return state

    def adjoint(self, state, load):
        free = self.layout.free_dofs
        solution = np.zeros_like(load)
        solution[free] = state.factor.solve(load[free])
        return solution

    def point_probe(self, x, y, angle):
        if not np.isfinite(angle):
            raise ValueError("probe angle must be finite")
        node = self._node(x, y)
        angle = np.deg2rad(angle)
        probe = np.zeros(self.layout.ndof)
        probe[2 * node:2 * node + 2] = [np.cos(angle), np.sin(angle)]
        return probe

    def probe_displacement(self, state, case, probe):
        return float(probe @ state.U[:, case])
