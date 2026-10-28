# heat_sink.py — the heat-sink benchmark: cool a uniformly heated plate through a small sink.
#
#   ┌─────────────────────────────┐
#   │   Q Q Q Q Q Q Q Q Q Q Q Q   │  every element generates heat uniformly, also the void ones
#   │   Q Q Q Q Q Q Q Q Q Q Q Q   │
#   │   Q Q Q Q Q Q Q Q Q Q Q Q   │  keep 40 % of the plate as conductor and lay it out so the
#   │   Q Q Q Q Q Q Q Q Q Q Q Q   │  heat reaches the sink with the lowest mean temperature
#   └──────────────(▪)────────────┘
#                  sink, T = 0
#
# A 100 x 100 mm square with unit conductivity in the solid and a thousandth of it
# in the void, heated uniformly over its whole area (the heat_source parameter of
# the q4_heat physics).  The only way out is a small heat sink, T = 0, in the
# middle of the bottom edge: a half-disc of radius 6 mm held at zero temperature
# and kept solid (a "fixed" hole in the scenario).  The design distributes 40 %
# conducting material to minimise the thermal compliance, which is proportional
# to the mean temperature: the tree-like conductors of the classic figure.
#
# The scenario is the same kind of scenario as a structural one: the supports
# are fixed temperatures, and Fmag of the load case is the point heat input.  It
# is zero here, because the heat comes from the source.
#
# Reference: Bendsoe & Sigmund 2003, section 1.5; Gersborg-Hansen, Bendsoe &
# Sigmund, Struct. Multidisc. Optim. 31 (2006) 251-259.

from toporia.framework import HoleConfig, LoadCase, Scenario, Solver

NAME = "Heat Sink"
ORDER = 90
ABOUT = ('A square plate heated uniformly over its whole area, cooled through one small sink in the'
         ' middle of an edge: distribute 40 % conductor to keep it as cool as possible.')
REFERENCE = ('The heat-sink problem of Bendsoe & Sigmund, Topology Optimization (Springer 2003), section'
             ' 1.5, as in Gersborg-Hansen, Bendsoe & Sigmund, Struct. Multidisc. Optim. 31 (2006) 251-259.'
             ' Papers: https://doi.org/10.1007/s00158-005-0584-3')


def scenario() -> Scenario:
    """The physical problem: plate, heat sink, uniform generation, conductor budget."""
    return Scenario(
        Lx=100.0,
        Ly=100.0,
        # The sink: a solid half-disc on the bottom edge, held at T = 0.
        holes=[HoleConfig(cx=50.0, cy=0.0, r_void=0.0, r_passive=6.0, kind="fixed")],
        # No point heat input: the heat is generated over the plate.
        load_cases=[LoadCase(Fmag=0.0, weight=1.0)],
        volfrac=0.4,
        objective={"type": "thermal_compliance"},
        # Conductivity of solid and of void (the scenario's E0 and Emin read as conductivities).
        E0=1.0,
        Emin=1e-3,
    )


def solver() -> Solver:
    """The solver settings recommended for this problem: a 50 x 50 mesh, optimality criteria."""
    return Solver(method="q4_heat+oc", filter_specs=[{"type": "density", "rmin": 1.5}], m=0.5, max_iter=300, tol=0.01)
