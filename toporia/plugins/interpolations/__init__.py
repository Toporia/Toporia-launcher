"""plugins.interpolations — material laws: how density becomes stiffness.

Every Interpolation subclass in this package with a non-empty `name` is found
by the INTERPOLATIONS registry.  A solver names one by type:
{"type": "ramp", "q": 8.0}.  See framework/parts/interpolation.py.

    simp.py   E = Emin + ρ^p (E0 − Emin)                (Bendsøe 1989)
    ramp.py   E = Emin + ρ / (1 + q(1 − ρ)) (E0 − Emin)  (Stolpe & Svanberg 2001)
"""

from toporia.framework.parts.interpolation import Interpolation
from toporia.framework.registry import Registry

INTERPOLATIONS = Registry("interpolation", Interpolation, __name__)

__all__ = ["INTERPOLATIONS", "Interpolation"]
