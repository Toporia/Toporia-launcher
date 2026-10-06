"""plugins.physics — finite element solvers and the physics engines built on them.

Each module here implements one physics on one element type, as plain
functions and as a framework.parts.physics.Physics engine that responses run on.

    q4_plane_stress.py   2-D linear elasticity, bilinear Q4 elements, SIMP
"""

from .q4_plane_stress import (
    Q4DofLayout,
    Q4PlaneStress,
    dof_layout,
    element_dofs,
    element_stiffness,
    element_stress_matrix,
    solve_fea,
)

__all__ = [
    "solve_fea",
    "dof_layout",
    "Q4DofLayout",
    "Q4PlaneStress",
    "element_stiffness",
    "element_stress_matrix",
    "element_dofs",
]
