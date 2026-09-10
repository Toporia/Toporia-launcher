"""library.fe — finite element solvers.

Each module here implements one physics on one element type.  Methods import
the solver they need directly; the engine never imports from this package.
"""

from .q4_plane_stress import (
    Q4DofLayout,
    dof_layout,
    element_dofs,
    element_stiffness,
    smooth_field,
    solve_fea,
)

__all__ = [
    "solve_fea",
    "dof_layout",
    "Q4DofLayout",
    "element_stiffness",
    "element_dofs",
    "smooth_field",
]
