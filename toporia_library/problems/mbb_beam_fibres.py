# toporia_library/problems/mbb_beam_fibres.py — the MBB beam with steered fibres.
#
# The MBB beam's scenario in a fibre-reinforced material (stiff along its fibres, a tenth
# as stiff across), where every element chooses its density and its fibre direction:
# the representation fibre_angle with the orthotropic Q4 engine (toporia_library/physics/
# q4_orthotropic.py).  The fibres turn to follow the members, so the beam is much stiffer
# than with fibres fixed along x.  A demonstration of several fields per element (Wave 5).

from toporia_core.framework import Solver

from . import mbb_beam

NAME = "MBB Beam (Fibre-steered)"
ORDER = 19
ABOUT = ("The MBB beam in a fibre-reinforced material, with the fibre direction chosen element by element"
         " along with the material layout.")
REFERENCE = ('Continuous fibre-angle optimisation with SIMP, as in T. Nomura, E. M. Dede, J. Lee, S. Yamasaki,'
             ' T. Matsumori, A. Kawamoto, N. Kikuchi, "General topology optimization method with continuous and'
             ' discrete orientation design using isoparametric projection", Int. J. Numer. Meth. Engng 101 (2015)'
             " 571-605. Demonstration preset. Papers: https://doi.org/10.1002/nme.4799")


def scenario():
    """The MBB beam's physical problem, unchanged."""
    return mbb_beam.scenario()


def solver() -> Solver:
    """Density and fibre angle per element, the orthotropic Q4 engine, a density filter and MMA."""
    return Solver(method="q4_orthotropic+mma", method_params={"move": 0.1},
                  representation={"type": "fibre_angle", "start_angle": 0.0},
                  filter_specs=[{"type": "density"}], m=1.0, max_iter=200, tol=0.01)
