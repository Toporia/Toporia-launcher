# plugins/postprocessors/export_stl.py — the design extruded to a solid, as STL.
#
# Every solid element of the black-and-white design becomes a block of the
# chosen thickness, and only the faces between solid and empty are written,
# so the result is one closed surface around the design exactly as it was
# analysed (stepped at the element size), ready for a slicer.  Binary STL, in
# millimetres.  Where two solid elements touch only at a corner, the surface
# touches itself along that edge; slicers accept this.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.postprocess import PostProcessor


def block_faces(solid, dx, dy, thickness):
    """Triangles (n, 3, 3) of the surface around the solid elements, outward-facing."""
    nely, nelx = solid.shape
    padded = np.pad(solid, 1, constant_values=False)
    quads = []
    rows, cols = np.nonzero(solid)
    for i, j in zip(rows, cols):
        x0, x1, y0, y1 = j * dx, (j + 1) * dx, i * dy, (i + 1) * dy
        quads.append([(x0, y0, 0), (x0, y1, 0), (x1, y1, 0), (x1, y0, 0)])                     # bottom
        quads.append([(x0, y0, thickness), (x1, y0, thickness), (x1, y1, thickness), (x0, y1, thickness)])  # top
        if not padded[i + 1, j]:          # left neighbour empty
            quads.append([(x0, y0, 0), (x0, y0, thickness), (x0, y1, thickness), (x0, y1, 0)])
        if not padded[i + 1, j + 2]:      # right
            quads.append([(x1, y0, 0), (x1, y1, 0), (x1, y1, thickness), (x1, y0, thickness)])
        if not padded[i, j + 1]:          # below
            quads.append([(x0, y0, 0), (x1, y0, 0), (x1, y0, thickness), (x0, y0, thickness)])
        if not padded[i + 2, j + 1]:      # above
            quads.append([(x0, y1, 0), (x0, y1, thickness), (x1, y1, thickness), (x1, y1, 0)])
    quads = np.asarray(quads, dtype=np.float32).reshape(-1, 4, 3)
    return np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])


def write_binary_stl(path, triangles):
    """A binary STL: 80-byte header, the count, then normal, three vertices and a spare word per triangle."""
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)
    record = np.zeros(len(triangles), dtype=[("normal", "<f4", 3), ("vertices", "<f4", (3, 3)), ("spare", "<u2")])
    record["normal"], record["vertices"] = normals, triangles
    with open(path, "wb") as file:
        file.write(b"Toporia design, mm".ljust(80, b" "))
        file.write(np.uint32(len(triangles)).tobytes())
        file.write(record.tobytes())


class ExportSTL(PostProcessor):
    """The black-and-white design extruded to a closed solid, as binary STL in millimetres."""

    name = "export_stl"
    label = "Export solid (STL)"
    order = 70
    table_metrics = ()          # files, not numbers to compare
    params = (Param("thickness", 5.0, "Thickness", "Extrusion depth of the 2-D design.",
                    min=0.01, max=1000.0, step=1.0, decimals=2, units="mm"),)

    def __init__(self, thickness=5.0):
        self.thickness = float(thickness)

    def process(self, result):
        problem = result.problem
        triangles = block_faces(result.solid(), problem.dx, problem.dy, self.thickness)
        write_binary_stl(result.file("design.stl"), triangles)
        return {"triangles": int(len(triangles)),
                "volume_mm3": float(result.solid().sum() * problem.dx * problem.dy * self.thickness)}
