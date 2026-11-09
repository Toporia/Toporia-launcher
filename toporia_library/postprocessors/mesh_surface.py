# toporia_library/postprocessors/mesh_surface.py — the design's own fitted boundary, from its mesh.
#
# A design optimised on an unstructured mesh (methods/unstructured.py) has cells that follow
# its holes.  This post-processor exports the boundary of its solid cells (density ≥ `level`)
# from that mesh, so curved holes come out curved instead of as the structured grid's steps:
#
#   3-D   the faces that belong to exactly one solid tetrahedron (a face shared by two solid
#         tetrahedra is inside the solid), oriented outward, written as a binary STL
#   2-D   the edges that belong to exactly one solid triangle, chained into closed loops
#         (outer boundaries and holes), written as DXF and SVG polylines
#
# A face or edge is found by sorting its node indices and counting how many solid cells
# contain it: count 1 is boundary.  Coordinates are in millimetres.  It runs only on a design
# that has a mesh of its own; on any other design its metrics are None and it writes nothing.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.postprocess import PostProcessor

from .export_dxf import dxf_text
from .export_stl import write_binary_stl
from .export_svg import svg_text


def boundary_loops(nodes, triangles):
    """Closed loops of the edges that belong to exactly one of `triangles`, as point lists."""
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    key = np.sort(edges, axis=1)
    _, first, counts = np.unique(key, axis=0, return_index=True, return_counts=True)
    boundary = edges[first[counts == 1]]
    following = {}
    for a, b in boundary:
        following.setdefault(int(a), []).append(int(b))
    loops, used = [], set()
    for a, b in boundary:
        if (int(a), int(b)) in used:
            continue
        loop, current, target = [int(a)], int(b), int(a)
        used.add((int(a), int(b)))
        while current != target and len(loop) <= len(boundary):
            loop.append(current)
            nxt = next((n for n in following.get(current, []) if (current, n) not in used), None)
            if nxt is None:
                break
            used.add((current, nxt))
            current = nxt
        loops.append([tuple(nodes[i]) for i in loop + [loop[0]]])
    return loops


class MeshSurface(PostProcessor):
    """The boundary of the solid cells of an unstructured-mesh design: STL in 3-D, DXF and SVG in 2-D."""

    name = "mesh_surface"
    label = "Fitted boundary from the mesh"
    use_when = ("After a run on an unstructured mesh: export the boundary that follows the holes, instead of the "
                "structured grid's steps.")
    reference = "Toporia's own: boundary faces and edges of the solid cells of the design's own mesh."
    order = 56
    dims = None
    table_metrics = ()
    params = (Param("level", 0.5, "Level", "Cells at or above this density are solid.", min=0.01, max=0.99,
                    step=0.05, decimals=3),)

    def __init__(self, level=0.5):
        self.level = float(level)

    def process(self, result):
        mesh = getattr(result, "mesh", None)
        if not mesh:
            return {"faces": None, "loops": None}
        nodes = np.asarray(mesh["nodes"], dtype=float)
        values = np.asarray(mesh["values"], dtype=float)
        if "tetrahedra" in mesh:
            from types import SimpleNamespace

            from toporia_library.physics.tet_mesh import solid_surface
            cells = SimpleNamespace(nodes=nodes, tets=np.asarray(mesh["tetrahedra"], dtype=int))
            triangles = solid_surface(cells, values, self.level).astype(np.float32)
            write_binary_stl(result.file("mesh_surface.stl"), triangles)
            return {"faces": int(len(triangles)), "loops": None}
        solid = np.asarray(mesh["triangles"], dtype=int)[values >= self.level]
        loops = boundary_loops(nodes, solid) if len(solid) else []
        problem = result.problem
        result.file("mesh_surface.dxf").write_text(dxf_text(loops), encoding="ascii")
        result.file("mesh_surface.svg").write_text(svg_text(loops, problem.Lx, problem.Ly, "evenodd"), encoding="utf-8")
        return {"faces": None, "loops": len(loops)}
