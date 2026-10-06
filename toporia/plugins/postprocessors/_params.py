# plugins/postprocessors/_params.py — parameters the exporters share.

from toporia.framework.params import Param

SOURCE = Param(
    "source", "auto", "Outline from",
    "Contour: the boundary of the black-and-white design, as analysed. Geometry: the "
    "representation's own shapes (moving morphable components' bars, uncut by the domain "
    "edge or holes). Auto: geometry when there is any, else the contour.",
    choices=(("auto", "Auto"), ("contour", "Contour of the design"), ("geometry", "Explicit geometry")))
