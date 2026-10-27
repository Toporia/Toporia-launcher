# plugins/problems/l_bracket.py — the L-bracket, the standard stress-concentration benchmark.
#
# An L-shaped domain: a 100 x 100 mm square with the top-right 60 x 60 mm
# removed, so both arms are 40 mm wide.  The top edge of the vertical arm is
# clamped and a downward point load acts at the free end of the horizontal arm.
#
#   (0,100) ───── (40,100)          clamped along the top of the vertical arm
#      |             |
#      |   design    |   (removed: 60 x 60, forced empty)
#      |             (40,40) ─────────────── (100,40)
#      |                                          |
#   (0,  0) ──────────────────────────────── (100, 0)
#                                       F ↓ at (100, 20)
#
# Why it matters: the re-entrant corner at (40, 40) is a stress singularity.
# A compliance objective happily leaves it sharp; the benchmark exists to show
# a stress constraint rounding it off.  Here the objective is compliance (what
# q4+oc can run); for the stress-limited version pair a model with an updater
# that takes a second constraint, e.g. q4+pymoto_mma, and add
# constraints=[{"type": "stress", "limit": ...}] (plugins/responses/README.md).
#
# The vertical arm's clamp uses the whole top edge; the nodes right of x = 40
# touch forced-empty elements with residual ersatz stiffness. This embedded-box
# support convention is a Toporia choice, not an exact removed-domain model.
#
# References: P. Duysinx, M. P. Bendsøe, "Topology optimization of continuum
# structures with local stress constraints", IJNME 43 (1998) 1453–1478;
# C. Le, J. Norato, T. Bruns, C. Ha, D. Tortorelli, "Stress-based topology
# optimization for continua", SMO 41 (2010) 605–620. These are stress-optimization
# references, not verified sources for this preset's dimensions or load point.

from toporia.framework import EdgeConstraint, EnforcedArea, LoadCase, PointLoad, Scenario, Solver

NAME = "L-bracket"
ORDER = 70
ABOUT = ('An L-shaped plate clamped along its top edge and loaded at the tip of its lower arm: the'
         ' standard stress benchmark, where a compliance design leaves the re-entrant corner sharp.')
REFERENCE = ('P. Duysinx and M. P. Bendsoe, Int. J. Numer. Meth. Eng. 43 (1998) 1453-1478; C. Le, J.'
             ' Norato, T. Bruns, C. Ha and D. Tortorelli, Struct. Multidisc. Optim. 41 (2010) 605-620.'
             ' Toporia chooses the 100 x 100 domain, 40-wide arms, unit tip load and 0.4 volume;'
             ' this is not a reproduction of the benchmarks in either paper.'
             ' Papers: https://doi.org/10.1002/%28SICI%291097-0207%2819981230%2943:8%3C1453::AID-NME480%3E3.0.CO%3B2-2 https://doi.org/10.1007/s00158-009-0440-y')


def scenario() -> Scenario:
    """The physical problem: domain, supports, loads, material, volume budget."""
    side, cut = 100.0, 60.0          # the square, and the corner taken out of it
    arm = side - cut                 # 40 mm wide arms
    return Scenario(
        Lx=side,
        Ly=side,
        edge_constraints=[EdgeConstraint(edge="top", dof="both")],
        # Forced empty: the removed top-right quadrant.
        enforced_areas=[EnforcedArea(points=[(arm, arm), (side, arm), (side, side), (arm, side)], kind="empty")],
        point_loads=[PointLoad(x=side, y=arm / 2.0)],     # mid-height of the arm's free end
        load_cases=[LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],   # downward
        volfrac=0.4,
    )


def solver() -> Solver:
    """The solver settings recommended for this problem."""
    # A coarser mesh than 1 el/mm keeps the first look quick; raise m to resolve the corner.
    return Solver(method="q4+oc", filter_specs=[{"type": "density"}], m=0.5, max_iter=100, tol=0.01)
