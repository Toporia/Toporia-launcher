"""Fixed-sharpness projection recipe using the existing density/Heaviside chain.

This is an independent recipe, not a port of Guest et al. (2011). The explicit
MMA settings come from Høghøj & Träff (2021), section 3.1, equation (11), which
credits Guest's asymptote-tightening approach. No optimizer formula is changed.
"""

from toporia.framework import Solver

from . import mbb_beam

NAME = "MBB Beam (Fixed Projection)"
ORDER = 16
ABOUT = ("MBB beam with fixed beta=16 projection and conservative MMA asymptotes. "
         "No beta continuation; sharpness and optimizer tuning remain problem dependent.")
REFERENCE = ("Independent fixed-projection recipe. MMA parameter recipe: Høghøj & Träff (2021), "
             "section 3.1, equation (11); continuation-free motivation: Guest, Asadpoure & Ha (2011). "
             "Papers: https://arxiv.org/abs/2102.12999 https://doi.org/10.1007/s00158-011-0676-1")


def scenario():
    """Use the ordinary MBB beam's physical problem."""
    return mbb_beam.scenario()


def solver() -> Solver:
    """Equal beta and beta_max disable the projection's built-in continuation."""
    beta = 16.0
    return Solver(
        method="q4+mma", m=1.0, max_iter=600, tol=0.001,
        method_params={"asyinit": 0.5 / (2 * beta + 1), "asyincr": 1.05,
                       "asydecr": 0.65, "move": 0.1},
        filter_specs=[{"type": "density", "rmin": 1.5},
                      {"type": "heaviside", "beta": beta, "beta_max": beta, "eta": 0.5}],
    )
