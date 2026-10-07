# plugins/postprocessors/export_dxf.py — the design's outline as DXF.
#
# Closed polylines in millimetres, in the plain R12 format that every CAD
# program and laser- or waterjet-cutting tool reads.  For a contour, outer
# boundaries and holes are both polylines and CAD tells them apart by nesting.
# Explicit shapes (moving morphable components) are one polyline per bar, cut
# to the domain; where bars overlap, join them in CAD (a union) before cutting.
# Written by hand, so no CAD library is needed.

from toporia.framework.parts.postprocess import PostProcessor

from ._measure import drawing
from ._params import SOURCE


def dxf_text(polygons):
    """An R12 DXF with one closed POLYLINE per polygon, on layer DESIGN, units mm."""
    lines = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
             "0", "SECTION", "2", "ENTITIES"]
    for polygon in polygons:
        lines += ["0", "POLYLINE", "8", "DESIGN", "66", "1", "70", "1"]
        for x, y in polygon[:-1]:                 # closed by the flag, not by repeating the start
            lines += ["0", "VERTEX", "8", "DESIGN", "10", f"{x:.6f}", "20", f"{y:.6f}"]
        lines += ["0", "SEQEND", "8", "DESIGN"]
    lines += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(lines) + "\n"


class ExportDXF(PostProcessor):
    """Outlines as closed DXF polylines in millimetres, for CAD and cutting."""

    name = "export_dxf"
    label = "Export outline (DXF)"
    order = 60
    table_metrics = ()          # files, not numbers to compare
    params = (SOURCE,)

    def __init__(self, source="auto"):
        self.source = source

    def process(self, result):
        polygons, used = drawing(result, self.source)
        result.file("design.dxf").write_text(dxf_text(polygons), encoding="ascii")
        return {"outlines": len(polygons), "from_geometry": used == "geometry"}
