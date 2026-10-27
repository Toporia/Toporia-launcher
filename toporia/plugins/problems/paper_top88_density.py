"""Figure 3(a), bottom panel: a dedicated paper recipe, not the generic MBB defaults."""

from dataclasses import replace

from . import mbb_beam
from ._research import PAPER, top88_description

NAME = "Paper: top88 Fig. 3(a) - Density"
ORDER = 200
ABOUT = "Recreate the 60 by 20 density-filtered half-MBB beam in Andreassen et al. Figure 3(a), bottom panel."
REFERENCE = "Andreassen et al., Efficient topology optimization in MATLAB using 88 lines of code (2011). Papers: " + PAPER
DESCRIPTION = top88_description("density")


def scenario():
    return replace(mbb_beam.scenario(), E0=1., Emin=1e-9, nu=.3)


def solver():
    return replace(mbb_beam.solver(), filter_specs=[{"type": "density", "rmin": 2.4}],
                   method_params={"move": .2}, interpolation={"type": "simp", "penal": 3.},
                   max_iter=200, tol=.01)
