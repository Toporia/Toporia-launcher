# plugins/postprocessors/export_svg.py — the design's outline as SVG.
#
# One path of closed outlines in millimetres (width and height carry the
# unit), with y turned the right way up for SVG.  A contour is filled with the
# even-odd rule, so holes are holes; explicit shapes (moving morphable
# components) with the non-zero rule, so overlapping bars fill as their union.
# Good for figures and the web; for CAD use the DXF export.

from toporia.framework.parts.postprocess import PostProcessor

from ._measure import drawing
from ._params import SOURCE


class ExportSVG(PostProcessor):
    """Outlines as an SVG drawing in millimetres."""

    name = "export_svg"
    label = "Export outline (SVG)"
    order = 50
    table_metrics = ()          # files, not numbers to compare
    params = (SOURCE,)

    def __init__(self, source="auto"):
        self.source = source

    def process(self, result):
        problem = result.problem
        polygons, used = drawing(result, self.source)
        width, height = problem.Lx, problem.Ly
        path = " ".join(
            "M " + " L ".join(f"{x:.4f},{height - y:.4f}" for x, y in polygon[:-1]) + " Z"
            for polygon in polygons)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}mm" height="{height:g}mm" '
               f'viewBox="0 0 {width:g} {height:g}">\n'
               f'  <rect width="{width:g}" height="{height:g}" fill="none" stroke="#999" stroke-width="0.1"/>\n'
               f'  <path d="{path}" fill="black" fill-rule="{"nonzero" if used == "geometry" else "evenodd"}"/>\n'
               f'</svg>\n')
        result.file("design.svg").write_text(svg, encoding="utf-8")
        return {"outlines": len(polygons), "from_geometry": used == "geometry"}
