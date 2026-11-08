# holes_and_rings.py — the test suite's plate with holes, solid rings and two load cases
#
# Not a benchmark: it is unlisted, so the GUI, the command line and the catalogue do not
# offer it.  The contract checks (`toporia check`) and the tests use it for what no listed
# preset has together: forced-void holes inside forced-solid rings, supports and loads on
# those rings, and a weighted pair of load cases.  The layout is that of the former Drone
# Arm preset, kept so the stored baselines still hold; the drone arm itself is an example
# project in examples/drone-arm/.
#
# Domain:  200 mm × 85 mm rectangular plate
# Fixed:   two central holes
# Load:    eight holes near the ends, equal +x and +y load cases

from toporia_core.framework import HoleConfig, LoadCase, Scenario, Solver

NAME = "Holes and Rings (test)"
ORDER = 1000
LISTED = False      # for the checks and tests only
ABOUT = ('A 200 x 85 mm plate fixed at two holes and loaded at eight, each hole inside a solid ring,'
         ' in two load cases. Used by the checks and tests.')
REFERENCE = "Toporia's own test geometry."


def scenario() -> Scenario:
    """The physical problem: domain, supports, loads, material, volume budget."""
    return Scenario(
        Lx=200.0,
        Ly=85.0,
        holes=[
            # Support holes — clamped (all DOFs fixed)
            HoleConfig(cx=85.1,  cy=75.0, r_void=3.0, r_passive=6.0, kind="fixed"),
            HoleConfig(cx=115.6, cy=75.0, r_void=3.0, r_passive=6.0, kind="fixed"),
            # Load holes
            HoleConfig(cx=7.9,   cy=17.6, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=15.2,  cy=8.9,  r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=16.6,  cy=24.9, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=23.8,  cy=16.2, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=192.8, cy=17.6, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=185.6, cy=8.9,  r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=184.2, cy=24.9, r_void=3.0, r_passive=6.0, kind="load"),
            HoleConfig(cx=176.9, cy=16.2, r_void=3.0, r_passive=6.0, kind="load"),
        ],
        load_cases=[
            LoadCase(Fmag=1.0, Fa=0.0,  weight=0.5),
            LoadCase(Fmag=1.0, Fa=90.0, weight=0.5),
        ],
        volfrac=0.5,
    )


def solver() -> Solver:
    """The default solver, run until the design settles (change below 0.01) or 200 steps."""
    return Solver(max_iter=200)
