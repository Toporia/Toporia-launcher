# plugins/postprocessors/export_stl.py — the design as a closed solid, as STL.
#
# Every solid element of the black-and-white design becomes a block — in 3-D
# the element itself, in 2-D the element extruded to the chosen thickness —
# and only the faces between solid and empty are written, so the result is
# one closed surface around the design exactly as it was analysed (stepped at
# the element size), ready for a slicer.  Binary STL, in millimetres.  Where
# two solid elements touch only along an edge or at a corner, the surface
# touches itself there; slicers accept this.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.postprocess import PostProcessor

#: For each of the six face directions (axis, side): the face's four corners, as
#: (x, y, z) offsets in {0, 1}, ordered so the face points outward.
_FACES = {
    (0, 0): ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)),     # x low
    (0, 1): ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),     # x high
    (1, 0): ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),     # y low
    (1, 1): ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),     # y high
    (2, 0): ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)),     # z low
    (2, 1): ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),     # z high
}


def voxel_faces(solid, spacing):
    """Triangles (n, 3, 3) of the closed surface around the solid voxels of a (z, y, x) array.

    `spacing` is the element size (dx, dy, dz).
    """
    solid = np.asarray(solid, dtype=bool)
    padded = np.pad(solid, 1, constant_values=False)
    nz, ny, nx = solid.shape
    z, y, x = np.nonzero(solid)
    quads = []
    for (axis, side), corners in _FACES.items():
        # The neighbour across this face, in the padded array (z, y, x order).
        step = [0, 0, 0]
        step[2 - axis] = 1 if side else -1
        open_face = ~padded[z + 1 + step[0], y + 1 + step[1], x + 1 + step[2]]
        if not np.any(open_face):
            continue
        base = np.stack([x[open_face], y[open_face], z[open_face]], axis=1).astype(float)
        quads.append(base[:, None, :] + np.array(corners, dtype=float)[None])
    if not quads:
        return np.zeros((0, 3, 3), dtype=np.float32)
    quads = np.concatenate(quads) * np.asarray(spacing, dtype=float)
    return np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]]).astype(np.float32)


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
    """The black-and-white design as a closed solid (a 2-D design extruded), binary STL in millimetres."""

    name = "export_stl"
    label = "Export solid (STL)"
    order = 70
    table_metrics = ()          # files, not numbers to compare
    dims = (2, 3)
    params = (Param("thickness", 5.0, "Thickness", "Extrusion depth of a 2-D design (a 3-D design has its own).",
                    min=0.01, max=1000.0, step=1.0, decimals=2, units="mm"),)

    def __init__(self, thickness=5.0):
        self.thickness = float(thickness)

    def process(self, result):
        problem = result.problem
        solid = result.solid()
        if solid.ndim == 2:
            solid, spacing = solid[None], (problem.dx, problem.dy, self.thickness)
        else:
            spacing = (problem.dx, problem.dy, problem.dz)
        triangles = voxel_faces(solid, spacing)
        write_binary_stl(result.file("design.stl"), triangles)
        return {"triangles": int(len(triangles)), "volume_mm3": float(solid.sum() * np.prod(spacing))}
