# column_buckling.py — a compressed column with a buckling constraint
#
# A slender block lying along x: clamped along its left edge, loaded by an axial
# compressive force at the middle of its free (right) end.  A compliance design
# of a block under axial load is simply a thick bar, which is cheap in
# compliance and says nothing about buckling; the load factor of the design
# (the multiple of the load at which it buckles) is what this problem limits.
#
#   (0, Ly) ────────────────────────────── (Lx, Ly)
#      |||                                        |
#      |||        [material domain]      ←── F ────   axial compression, mid-height
#      |||                                        |
#   (0,  0) ────────────────────────────── (Lx,  0)
#   clamped                                 free end
#
# The column lies along x, following the parent Q4 engine's coordinate convention.
#
# Objective compliance, constraint: the lowest buckling load factor must be at
# least 1 (min_load) times the applied load.  The constraint needs an updater
# that takes a second constraint: the preset uses pyMOTO's MMA. Change the
# objective to "buckling_load" to maximise the load
# factor at the given volume instead.
#
# Reference: F. Ferrari, O. Sigmund, J. K. Guest, "Topology optimization with
# linearized buckling criteria in 250 lines of Matlab", SMO 63 (2021) 3045-3066.
# The paper's own column dimensions were not available when this was written;
# the geometry here is Toporia's own.

from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario, Solver

NAME = "Column Buckling"
ORDER = 80
ABOUT = ('A 60 x 20 mm column clamped at one end and compressed axially at the other: minimise'
         ' compliance while the buckling load factor stays above a limit.')
REFERENCE = ('Linearised buckling in topology optimisation: F. Ferrari, O. Sigmund and J. K. Guest,'
             ' Struct. Multidisc. Optim. 63 (2021) 3045-3066. Geometry is Toporia\'s own.'
             ' Papers: https://doi.org/10.1007/s00158-021-02854-x')


def scenario() -> Scenario:
    """The physical problem: domain, supports, loads, material, volume budget, buckling constraint."""
    Lx, Ly = 60.0, 20.0
    return Scenario(
        Lx=Lx,
        Ly=Ly,
        edge_constraints=[EdgeConstraint(edge="left", dof="both")],
        point_loads=[PointLoad(x=Lx, y=Ly / 2.0)],
        # Fa = 180 degrees points toward the clamp: compression.
        load_cases=[LoadCase(Fmag=0.1, Fa=180.0, weight=1.0)],
        volfrac=0.3,
        objective={"type": "compliance"},
        constraints=[{"type": "buckling_load", "min_load": 1.0}],
    )


def solver() -> Solver:
    """The solver settings recommended for this problem."""
    return Solver(
        method="q4_buckling+pymoto_mma",
        filter_specs=[{"type": "density"}, {"type": "heaviside", "beta": 1.0, "eta": 0.5}],
        schedules=[{"path": "filters[1].beta", "type": "geometric", "start": 1.0, "end": 8.0,
                    "factor": 2.0, "every": 30}],
        m=1.0, max_iter=300, tol=0.01,
    )
