# vibrating_beam.py — a clamped-clamped beam with a payload, maximising its fundamental frequency.
#
# The benchmark of Du & Olhoff (2007): a beam 8 times as long as it is deep, clamped at both
# ends, carrying a non-structural mass at its centre.  With half of the domain filled,
# the design that vibrates slowest-to-fastest is the one that puts material where the
# first bending mode bends most and ties the payload firmly to both walls.
#
#   |▓▓                                               ▓▓|
#   |▓▓            [ material domain ]   (payload ●)  ▓▓|
#   |▓▓                                               ▓▓|
#   clamped                                         clamped
#
# The payload is declared as a point load: the engine hangs its `attached_mass` on the load
# nodes (the load itself plays no part in the vibration).  Because eigenvalue sensitivities
# change sign, the run uses MMA; OC cannot follow them.
#
# Settings: 80 x 10 elements (10 el/mm), volume fraction 0.5, payload mass 2 (the solid beam
# has mass 8), the default mass fix of Pedersen (threshold 0.1, exponent 6), the three
# lowest eigenvalues taken together so a second mode that catches up is raised as well.

from toporia.framework import EdgeConstraint, LoadCase, PointLoad, Scenario, Solver

NAME = "Vibrating Beam"
ORDER = 80
ABOUT = ('A beam clamped at both ends, carrying a payload at its centre: maximise its lowest natural'
         ' frequency with the volume fixed.')
REFERENCE = ('After J. Du, N. Olhoff, "Topological design of freely vibrating continuum structures for maximum'
             ' values of simple and multiple eigenfrequencies and frequency gaps", Struct. Multidisc. Optim. 34'
             ' (2007) 91-110, with the mass interpolation of N. L. Pedersen, Struct. Multidisc. Optim. 20 (2000)'
             ' 2-11.'
             ' Papers: https://doi.org/10.1007/s00158-007-0101-y https://doi.org/10.1007/s001580050130')


def scenario() -> Scenario:
    """The physical problem: the clamped beam, the payload's position, and what is maximised."""
    return Scenario(
        Lx=8.0, Ly=1.0,
        edge_constraints=[EdgeConstraint(edge="left", dof="both"), EdgeConstraint(edge="right", dof="both")],
        point_loads=[PointLoad(x=4.0, y=0.5)],     # where the payload hangs; the force itself is unused
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],
        volfrac=0.5,
        objective={"type": "eigenfrequency", "modes": 3, "p": 16.0},
    )


def solver() -> Solver:
    """The solver settings recommended for this problem."""
    return Solver(method="q4_dynamic+mma", method_params={"attached_mass": 2.0},
                  filter_specs=[{"type": "density", "rmin": 1.5}], m=10.0, max_iter=300, tol=0.001)
