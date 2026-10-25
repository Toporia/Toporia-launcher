# plugins/physics/h8_heat.py — 3-D steady heat conduction on eight-node bricks.
#
# The scalar counterpart of h8_solid.py: the same BoxProblem, the same brick
# numbering (C order over z, y, x), one temperature per node.  The assembly,
# the solve and the answers to the Physics interface are in _conduction.py;
# this file supplies the 8 × 8 element matrix
#
#     K_e = ∫ ∇Nᵀ ∇N dV       (unit conductivity)
#
# integrated with 2 × 2 × 2 Gauss points over a dx × dy × dz brick.  Unlike in
# 2-D, K_e scales with the element's length, so the real sizes are used.
#
# Supports (the faces and lines of the scenario's constraints) are heat sinks
# at T = 0; point loads are lines of heat input through the depth.
#
# Reference: Bendsøe & Sigmund, Topology Optimization (2003), section 1.5;
# Gersborg-Hansen, Bendsøe & Sigmund, Struct. Multidisc. Optim. 31 (2006)
# 251-259 (https://doi.org/10.1007/s00158-005-0584-3).

import numpy as np

from toporia.framework.parts.physics import THERMAL_ENERGY
from toporia.plugins.physics.h8_solid import CORNERS, element_dofs

from ._conduction import Conduction


def element_conductivity(dx=1.0, dy=1.0, dz=1.0):
    """8 × 8 conductivity matrix of one brick at unit conductivity, 2 × 2 × 2 Gauss points."""
    c = np.array(CORNERS, dtype=float)
    g = 1.0 / np.sqrt(3.0)
    KE = np.zeros((8, 8))
    for xi in (-g, g):
        for eta in (-g, g):
            for zeta in (-g, g):
                gradient = np.stack([
                    c[:, 0] * (1 + c[:, 1] * eta) * (1 + c[:, 2] * zeta) / 8 * (2.0 / dx),
                    c[:, 1] * (1 + c[:, 0] * xi) * (1 + c[:, 2] * zeta) / 8 * (2.0 / dy),
                    c[:, 2] * (1 + c[:, 0] * xi) * (1 + c[:, 1] * eta) / 8 * (2.0 / dz),
                ])
                KE += gradient.T @ gradient * (dx * dy * dz / 8.0)
    return KE


class H8Heat(Conduction):
    """Steady heat conduction in 3-D on eight-node bricks, conductivity from the material law."""

    name = "h8_heat"
    label = "3-D H8 heat conduction (Toporia)"
    order = 40
    provides = (THERMAL_ENERGY,)
    dims = (3,)
    element_order = "C"

    def _discretise(self, problem):
        if getattr(problem, "dims", 2) != 3:
            raise ValueError("the H8 heat engine needs a 3-D problem: give the scenario a depth Lz > 0")
        nodes = element_dofs(problem)[:, ::3] // 3        # the first DOF of each node is 3 × its number
        node_ids = np.arange(problem.nn).reshape(tuple(n + 1 for n in problem.shape))
        measure = problem.dx * problem.dy * problem.dz
        return element_conductivity(problem.dx, problem.dy, problem.dz), nodes, measure, node_ids
