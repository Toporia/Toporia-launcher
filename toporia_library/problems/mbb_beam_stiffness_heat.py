# plugins/problems/mbb_beam_stiffness_heat.py — one design, two physics: stiff and cool.
#
# The MBB beam's scenario with a second physics on the same design field
# (framework/companions.py): steady heat conduction, with its own material law (linear,
# p = 1) and void a thousandth of solid.  The load point is read by the heat engine as
# the heat source and the supports as the sinks.  A variable measures the thermal
# compliance on that physics, and a combined objective weighs it against the structural
# compliance.  The two fields are not coupled: one design serves both.
#
# MMA, because the combined sensitivities are not all of one sign.

from toporia_core.framework import Solver

from . import mbb_beam

NAME = "MBB Beam (Stiffness and Heat)"
ORDER = 17
ABOUT = ("One design for two physics: the MBB beam made stiff and, with a heat conduction solved on the same"
         " design, good at carrying heat from the load point to the supports.")
REFERENCE = ("Multi-physics weighted-sum design on one density field, as in thermo-mechanical topology"
             " optimisation: T. Gao, W. Zhang, Int. J. Numer. Meth. Engng 82 (2010) 1451-1474."
             " Demonstration preset; physics combined through the objective, not coupled."
             " Papers: https://doi.org/10.1002/nme.2802")


def scenario():
    """The MBB beam with a heat physics on the same design, both in the objective."""
    from dataclasses import replace
    return replace(
        mbb_beam.scenario(),
        extra_physics=[{"model": "q4_heat", "interpolation": {"type": "simp", "penal": 1.0}}],
        variables=[{"name": "heat", "type": "thermal_compliance", "physics": "q4_heat"}],
        objective={"type": "combined", "combine": "sum",
                   "terms": [{"type": "compliance", "weight": 1.0},
                             {"type": "variable", "variable": "heat", "weight": 0.5}]})


def solver() -> Solver:
    """MMA with a density filter on the classic 60 x 20 mesh."""
    return Solver(method="q4+mma", filter_specs=[{"type": "density"}], m=1.0, max_iter=200, tol=0.01)
