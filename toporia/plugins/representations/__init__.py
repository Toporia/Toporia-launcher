"""plugins.representations — what the design variables are.

Every Representation subclass in this package with a non-empty `name` is
found by the REPRESENTATIONS registry.  A solver names one by type:
{"type": "mmc", "n_x": 4}.  See framework/parts/representation.py.

    element_density.py   one density per element (the classic; the default)
    mmc.py               moving morphable components: bars by position, length,
                         thickness and angle (Guo, Zhang & Zhong 2014); with
                         thickness = variable the thickness changes along each
                         bar (Zhang, Yuan, Zhang & Guo 2016)
    bspline.py           a coarse grid of B-spline coefficients, evaluated at the
                         element centres (Qian 2013)
    neural.py            independent TOuNN-style tanh coordinate network with
                         explicit NumPy backpropagation, in 2-D and 3-D
    mmv.py               moving superelliptical holes, the restricted 2-D dual
                         of MMC (MMV framework: Zhang et al. 2017)
    geometry_projection.py  fixed-radius capsules with floating endpoints and
                            component activation, in 2-D and 3-D (Norato et al. 2015)
"""

from toporia.framework.parts.representation import Representation
from toporia.framework.registry import Registry

REPRESENTATIONS = Registry("representation", Representation, __name__)

__all__ = ["REPRESENTATIONS", "Representation"]
