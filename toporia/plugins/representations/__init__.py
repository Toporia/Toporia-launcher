"""plugins.representations — what the design variables are.

Every Representation subclass in this package with a non-empty `name` is
found by the REPRESENTATIONS registry.  A solver names one by type:
{"type": "mmc", "n_x": 4}.  See framework/parts/representation.py.

    element_density.py   one density per element (the classic; the default)
    mmc.py               moving morphable components: bars by position, length,
                         thickness and angle (Guo, Zhang & Zhong 2014)
"""

from toporia.framework.parts.representation import Representation
from toporia.framework.registry import Registry

REPRESENTATIONS = Registry("representation", Representation, __name__)

__all__ = ["REPRESENTATIONS", "Representation"]
