# plugins/problems/truss_mbb.py — the MBB beam as a truss, then rounded off for stress.
#
# The MBB beam's scenario solved by the ground-structure truss method (methods/truss.py):
# nodes every 5 mm, bars to neighbours up to two steps away, sized for minimum compliance
# under the volume budget.  The settled truss is drawn as a density and handed to a
# density optimisation of the peak von Mises stress (q4 + MMA) that starts from it.
#
# Measured: the truss settles near compliance 141 (bars, so not comparable with the
# continuum's 188), its drawn density has a peak stress near 6.5, and the stress stage
# brings that to about 1.8 within 60 iterations.

from toporia_core.framework import Solver

from . import mbb_beam

NAME = "MBB Beam (Truss)"
ORDER = 18
ABOUT = ("The MBB beam found as a truss on a ground structure first, then drawn as a density and rounded off"
         " for a low peak stress by a continuum optimisation that starts from it.")
REFERENCE = ('W. S. Dorn, R. E. Gomory, H. J. Greenberg, "Automatic design of optimal structures", J. Mécanique'
             " 3 (1964) 25-52; minimum-compliance truss sizing as in Bendsoe & Sigmund (2003), sec. 4.1."
             " Two-stage recipe chosen here. Papers: https://doi.org/10.1007/978-3-662-05086-6")


def scenario():
    """The MBB beam's physical problem, unchanged."""
    return mbb_beam.scenario()


def solver() -> Solver:
    """The truss method, then the stress stage."""
    return Solver(method="truss", method_params={"spacing": 5.0, "reach": 2, "stage": "stress",
                                                 "truss_iterations": 80},
                  filter_specs=[], m=1.0, max_iter=200, tol=0.01)


def _description():
    from ._truss_description import truss_description
    return truss_description(__import__(__name__, fromlist=["x"]),
                             "the truss is drawn as a density and a q4 + MMA optimisation of the peak von Mises "
                             "stress (p-norm) starts from it, with a density filter and the same volume budget.")
