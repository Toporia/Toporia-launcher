# apps/gui/geometry_import.py — geometry-only imports into portable editor objects.
# Imported triangle coordinates are embedded; no runtime dependency on source paths.

from pathlib import Path

import numpy as np

from .geometry import make_object


def import_stl(path, role="void"):
    """Read STL geometry, preserving physical coordinates and source filename."""
    try:
        import pyvista as pv
    except ImportError as error:
        raise ValueError("Install the optional geometry dependencies: pip install -e '.[gui3d]'") from error
    mesh = pv.read(path).triangulate().clean()
    if not mesh.n_cells or mesh.n_cells > 500_000:
        raise ValueError("STL must contain between 1 and 500,000 triangles; simplify a larger mesh before importing")
    origin = np.asarray(mesh.bounds).reshape(3, 2)[:, 0]
    vertices = np.asarray(mesh.points, dtype=float) - origin
    faces = mesh.faces.reshape(-1, 4)[:, 1:]
    sampling = "volume" if mesh.is_manifold and not mesh.n_open_edges else "surface"
    return make_object("stl", tuple(origin), (1, 1, 1), role,
                       name=Path(path).stem, source=Path(path).name, vertices=vertices.tolist(),
                       faces=faces.tolist(), sampling=sampling)


def import_dxf(path, role="void"):
    """Import closed planar polylines and circles; reject unsupported entities explicitly."""
    try:
        import ezdxf
    except ImportError as error:
        raise ValueError("DXF import needs the optional gui3d dependencies") from error
    objects = []
    for entity in ezdxf.readfile(path).modelspace():
        kind = entity.dxftype()
        if kind == "CIRCLE":
            cx, cy, cz = entity.dxf.center
            if abs(cz) > 1e-8:
                raise ValueError("DXF circles must lie in the XY plane")
            objects.append(make_object("circle", (cx, cy, 0), (2 * entity.dxf.radius,) * 3,
                                       role, name=Path(path).stem))
        elif kind == "LWPOLYLINE" and entity.closed:
            if entity.has_arc or abs(entity.dxf.elevation) > 1e-8:
                raise ValueError("DXF polylines must be straight and lie in the XY plane")
            vertices = [[float(x), float(y)] for x, y in entity.get_points("xy")]
            objects.append(make_object("polygon", role=role, name=Path(path).stem, vertices=vertices))
        else:
            raise ValueError(f"DXF entity {kind} is unsupported; export closed straight XY polylines or circles")
    if not objects:
        raise ValueError("DXF contains no supported geometry")
    return objects
