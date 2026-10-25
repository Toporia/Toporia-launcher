"""plugins.physics — finite element solvers and the physics engines built on them.

Each module here implements one physics on one element type, as plain
functions and as a framework.parts.physics.Physics engine that responses run on.

    q4_plane_stress.py   2-D linear elasticity, bilinear Q4 elements, SIMP
    h8_solid.py          3-D linear elasticity, trilinear bricks
    q4_heat.py           2-D steady heat conduction, bilinear Q4 elements
    h8_heat.py           3-D steady heat conduction, trilinear bricks
    _conduction.py       what the two heat engines share
    q4_nonlinear.py      2-D large-displacement elasticity, Q4, Newton with load steps
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
