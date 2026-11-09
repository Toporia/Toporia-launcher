# plugins/problems/truss_mbb.py — the MBB beam as a truss, made into a clean solid.
#
# The MBB beam's scenario solved by the ground-structure truss method (methods/truss.py):
# nodes every 5 mm, bars to neighbours up to two steps away, sized for minimum compliance
# under the volume budget.  The design stays bars; at the end the post-processor
# truss_solid makes them into one outline (DXF and SVG): bar capsules joined by round
# nodes.  The truss settles near compliance 141 (bars carry only axial force, so this is
# not comparable with the continuum's 188).

from toporia_core.framework import Solver
from toporia_core.framework.problem.run import Output

from . import mbb_beam

NAME = "MBB Beam (Truss)"
ORDER = 18
ABOUT = ("The MBB beam found as a truss on a ground structure, kept as bars, and made into a clean solid"
         " outline at the end.")
REFERENCE = ('W. S. Dorn, R. E. Gomory, H. J. Greenberg, "Automatic design of optimal structures", J. Mécanique'
             " 3 (1964) 25-52; minimum-compliance truss sizing as in Bendsoe & Sigmund (2003), sec. 4.1."
             " Papers: https://doi.org/10.1007/978-3-662-05086-6")


def scenario():
    """The MBB beam's physical problem, unchanged."""
    return mbb_beam.scenario()


def solver() -> Solver:
    """The truss method on a 5 mm ground structure."""
    return Solver(method="truss", method_params={"spacing": 5.0, "reach": 2},
                  filter_specs=[], m=1.0, max_iter=150, tol=1e-3)


def output() -> Output:
    """At the end: the bars as one clean outline."""
    return Output(postprocess=[{"type": "truss_solid"}])


def _description():
    from ._truss_description import truss_description
    return truss_description(__import__(__name__, fromlist=["x"]),
                             "the post-processor truss_solid joins the bars into one outline: capsules as wide as "
                             "their areas, round joints, traced from their signed distance field.")
