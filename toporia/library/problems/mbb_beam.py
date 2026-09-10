# mbb_beam.py — MBB beam benchmark (Messerschmitt-Bölkow-Blohm)
#
# This is THE canonical topology-optimisation benchmark, used in virtually
# every paper that introduces a new algorithm or filter.  It models the left
# half of a simply-supported beam loaded at its centre, exploiting symmetry.
#
# Boundary conditions (half-model, left half of a 2:1 full beam):
#
#   (0, Ly) ──── F↓ ─────────────────── (Lx, Ly)
#      |                                       |
#      |           [material domain]           |
#      |                                       |
#   (0,  0) ─────────────────────────── (Lx,  0)
#    x=fixed                              y=fixed
#    (symmetry)                           (roller)
#
#   Left edge  — x-DOF constrained (symmetry plane: no horizontal movement)
#   Top-left   — downward point load  (= centre of the full beam)
#   Bottom-right corner — y-DOF constrained (roller support)
#
# Reference (Andreassen et al. 2011, top88 MATLAB code):
#   nelx=60, nely=20, volfrac=0.5, penal=3, rmin=1.5
#   Converged compliance ≈ 188 (normalised units, F=1)
#
# Coordinate convention — origin at the bottom-left corner:
#   (0, Ly) ─── top-left    (Lx, Ly) ─── top-right
#   (0,  0) ─── bottom-left (Lx,  0) ─── bottom-right

from toporia.core.config import EdgeConstraint, LoadCase, PointConstraint, PointLoad, TopOptConfig


def get_config() -> TopOptConfig:
    Lx, Ly = 60.0, 20.0

    return TopOptConfig(
        Lx=Lx,
        Ly=Ly,
        m=1.0,

        holes=[],

        edge_constraints=[
            # Left edge: x-DOF fixed — this is the symmetry plane of the full beam.
            # Nodes on the symmetry plane cannot move horizontally, but can move vertically.
            EdgeConstraint(edge="left", dof="x"),
        ],
        point_constraints=[
            # Bottom-right corner: y-DOF fixed — roller support at the beam end.
            PointConstraint(x=Lx, y=0.0, dof="y"),
        ],
        point_loads=[
            # Top-left corner: this is the centre of the full beam in the symmetric model.
            PointLoad(x=0.0, y=Ly),
        ],

        # Fa=270° = downward (-y direction).
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],

        volfrac=0.5,
        filter_specs=[{"type": "density"}],
        max_iter=100,
        tol=0.01,
    )
