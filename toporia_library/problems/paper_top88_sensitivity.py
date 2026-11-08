"""Figure 3(a), top panel: sensitivity filtering with the paper's radius."""

from dataclasses import replace

from . import paper_top88_density
from ._research import PAPER, top88_description

NAME = "Paper: top88 Fig. 3(a) - Sensitivity"
ORDER = 201
ABOUT = "Recreate the 60 by 20 sensitivity-filtered half-MBB beam in Andreassen et al. Figure 3(a), top panel."
REFERENCE = "Andreassen et al., Efficient topology optimization in MATLAB using 88 lines of code (2011). Papers: " + PAPER
DESCRIPTION = top88_description("sensitivity")


def scenario():
    return paper_top88_density.scenario()


def solver():
    return replace(paper_top88_density.solver(), filter_specs=[{"type": "sensitivity", "rmin": 2.4}])
