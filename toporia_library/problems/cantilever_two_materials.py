# toporia_library/problems/cantilever_two_materials.py — a cantilever of two materials (DMO).
#
# The cantilever's scenario, but every element chooses between void, a stiff heavy material
# (stiffness 1, mass 1) and a soft light one (stiffness 0.4, mass 0.3), through the
# multi-material representation and the DMO law (toporia_library/interpolations/dmo.py).  The
# volume budget bounds the mass, so the light material is cheap: the optimum puts the
# stiff material where the bending stress is high (top and bottom, near the support) and
# the light one in the web.  A demonstration of several fields per element (Wave 5).

from dataclasses import replace

from toporia_core.framework import Solver

from . import cantilever

NAME = "Cantilever (Two Materials)"
ORDER = 21
ABOUT = ("The cantilever made of two materials: each element is void, a stiff heavy material or a soft light"
         " one, and the mass budget decides where each goes.")
REFERENCE = ('Discrete material optimisation: J. Stegmann, E. Lund, "Discrete material optimization of general'
             ' composite shell structures", Int. J. Numer. Meth. Engng 62 (2005) 2009-2027. Demonstration preset;'
             " materials chosen here. Papers: https://doi.org/10.1002/nme.1259")


def scenario():
    """The cantilever, with a mass budget of 40 %."""
    return replace(cantilever.scenario(), volfrac=0.4)


def solver() -> Solver:
    """Density and material weights per element, the DMO law, a density filter and MMA."""
    return Solver(method="q4+mma", method_params={"move": 0.1},
                  representation={"type": "multi_material", "materials": 2},
                  interpolation={"type": "dmo", "stiffness_2": 0.4, "mass_2": 0.3},
                  filter_specs=[{"type": "density"}], m=1.0, max_iter=200, tol=0.01)
