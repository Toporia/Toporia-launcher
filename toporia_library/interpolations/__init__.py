"""plugins.interpolations — material laws: how density becomes stiffness.

Every Interpolation subclass in this package with a non-empty `name` is found
by the INTERPOLATIONS registry.  A solver names one by type:
{"type": "ramp", "q": 8.0}.  See framework/parts/interpolation.py.

    simp.py   E = Emin + ρ^p (E0 − Emin)                (Bendsøe 1989)
    ramp.py   E = Emin + ρ / (1 + q(1 − ρ)) (E0 − Emin)  (Stolpe & Svanberg 2001)
    ordered_simp.py   piecewise SIMP between ordered materials   (Zuo & Saitou 2017)
    sinh.py   linear stiffness and hyperbolic-sine effective volume (Bruns 2005)
    hashin_shtrikman.py   fixed-nu envelope of elastic HS upper bounds, 2-D/3-D
"""

from toporia_core.framework.parts.interpolation import Interpolation

# The registry lives in the core; this package is one of its sources (pyproject entry points).
from toporia_core.framework.registries import INTERPOLATIONS  # noqa: E402

__all__ = ["INTERPOLATIONS", "Interpolation"]
