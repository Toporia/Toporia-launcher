"""plugins.postprocessors — what is made of a finished design.

Every PostProcessor subclass in this package with a non-empty `name` is found
by the POSTPROCESSORS registry.  A run lists the ones to apply in
output.postprocess: [{"type": "threshold"}, {"type": "export_dxf"}].
See framework/parts/postprocess.py.

    threshold.py     black and white at the same volume, and its compliance
    connectivity.py  islands, and whether every load reaches a support
    feature_size.py  the thinnest member and the smallest hole
    export_svg.py    outlines as SVG (figures, the web)
    export_dxf.py    outlines as DXF (CAD, laser and waterjet cutting)
    export_stl.py    the design extruded to a solid, as STL (3-D printing)
    _measure.py      shared: the referee compliance, contours, image files
"""

from toporia.framework.parts.postprocess import PostProcessor, Result
from toporia.framework.registry import Registry

POSTPROCESSORS = Registry("postprocessor", PostProcessor, __name__)

__all__ = ["POSTPROCESSORS", "PostProcessor", "Result"]
