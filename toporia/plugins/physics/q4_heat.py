# plugins/physics/q4_heat.py — 2-D steady heat conduction on bilinear Q4 elements.
#
# The scalar counterpart of q4_plane_stress.py: the same structured grid and
# the same element numbering, but one temperature per node instead of two
# displacements.  The assembly, the solve and the answers to the Physics
# interface are in _conduction.py; this file only supplies the 4 × 4 element
# conductivity matrix
#
#     K_e = ∫ ∇Nᵀ ∇N dA        (unit conductivity, unit thickness)
#
# integrated with 2 × 2 Gauss points over a dx × dy rectangle.  For a square
# element it is the classic (1/6)·[[4,−1,−2,−1],[−1,4,−1,−2],[−2,−1,4,−1],[−1,−2,−1,4]].
# Like the 2-D elasticity matrix it does not change when the element is scaled
# uniformly: only the aspect ratio dx/dy matters.
#
# Reference: M. P. Bendsøe, O. Sigmund, Topology Optimization (2003), section 1.5;
# A. Gersborg-Hansen, M. P. Bendsøe, O. Sigmund, Struct. Multidisc. Optim. 31
# (2006) 251-259 (https://doi.org/10.1007/s00158-005-0584-3).

import numpy as np

from toporia.framework.parts.physics import THERMAL_ENERGY
from toporia.plugins.physics.q4_plane_stress import element_dofs

from ._conduction import Conduction

#: Corners of the reference square in the element's node order.  The elasticity
#: engine numbers an element top-left, top-right, bottom-right, bottom-left
#: (element_dofs), and the heat engine shares that numbering.
CORNERS = ((-1, 1), (1, 1), (1, -1), (-1, -1))


def element_conductivity(dx=1.0, dy=1.0, thickness=1.0):
    """4 × 4 conductivity matrix of one rectangle at unit conductivity, 2 × 2 Gauss points.

    Nodes in the order of CORNERS.  `thickness` multiplies the whole matrix.
    """
    gauss = (-1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0))
    KE = np.zeros((4, 4))
    for xi in gauss:
        for eta in gauss:
            dN_dxi = np.array([cx * (1 + cy * eta) / 4 for cx, cy in CORNERS])
            dN_deta = np.array([cy * (1 + cx * xi) / 4 for cx, cy in CORNERS])
            gradient = np.stack([dN_dxi * (2.0 / dx), dN_deta * (2.0 / dy)])   # 2 × 4
            KE += gradient.T @ gradient * (dx / 2.0) * (dy / 2.0) * thickness
    return KE


class Q4Heat(Conduction):
    """Steady heat conduction, 2-D, bilinear Q4 elements, conductivity from the material law.

    Supports are heat sinks (T = 0), the load case's magnitude is heat entering
    at the load points, and `heat_source` is generated uniformly everywhere.
    Answers THERMAL_ENERGY: the thermal compliance and its element energies.
    """

    name = "q4_heat"
    label = "2-D Q4 heat conduction (Toporia)"
    order = 30
    provides = (THERMAL_ENERGY,)
    dims = (2,)
    element_order = "F"          # elements are numbered column by column, as in q4_plane_stress

    def _discretise(self, problem):
        nodes = element_dofs(problem)[:, ::2] // 2        # the first DOF of each node is 2 × its number
        node_ids = np.arange(problem.nn).reshape((problem.nely + 1, problem.nelx + 1), order="F")
        return element_conductivity(problem.dx, problem.dy), nodes, problem.dx * problem.dy, node_ids
