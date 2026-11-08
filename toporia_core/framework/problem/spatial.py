# framework/problem/spatial.py — physical transforms and portable triangular regions.
# STL triangles are embedded as plain vertices/faces, so .pro/.top files remain
# self-contained. VTK supplies geometry queries; it is imported only for STL work.

import numpy as np


def rotation_matrix(angles):
    """Local-to-world Euler XYZ rotation, applied as Rz @ Ry @ Rx."""
    x, y, z = np.deg2rad(angles)
    cx, cy, cz = np.cos([x, y, z])
    sx, sy, sz = np.sin([x, y, z])
    return (np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
            @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
            @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]))


def local_coordinates(obj, coordinates):
    """Transform world coordinates into an object's unscaled physical frame."""
    return (coordinates - np.asarray(obj["position"])) @ rotation_matrix(obj["rotation"])


def triangle_mesh(obj, transformed=True):
    """Recreate an embedded triangle mesh without any external file references."""
    try:
        import pyvista as pv
    except ImportError as error:
        raise ValueError("STL regions need the optional gui3d dependencies: pip install -e '.[gui3d]'") from error
    points = np.asarray(obj.get("vertices", []), dtype=float)
    if np.any(np.asarray(obj["size"]) <= 0):
        raise ValueError("STL scale factors must be positive")
    faces = np.asarray(obj.get("faces", []))
    if points.ndim != 2 or points.shape[1] != 3 or not len(points) or not np.isfinite(points).all():
        raise ValueError("STL vertices must be finite XYZ triples")
    if faces.ndim != 2 or faces.shape[1] != 3 or not len(faces) or not np.issubdtype(faces.dtype, np.integer):
        raise ValueError("STL faces must be triangle vertex indices")
    if faces.min() < 0 or faces.max() >= len(points):
        raise ValueError("STL face refers to a missing vertex")
    if transformed:
        points = (points * np.asarray(obj["size"])) @ rotation_matrix(obj["rotation"]).T + np.asarray(obj["position"])
    cells = np.column_stack((np.full(len(faces), 3), faces)).ravel()
    return pv.PolyData(points, cells).clean()


def stl_mask(obj, coordinates, tolerance, nodes):
    """Select a closed STL volume or nodes close to an open/closed surface patch."""
    import pyvista as pv
    mesh = triangle_mesh(obj)
    query = pv.PolyData(coordinates.reshape(-1, 3))
    sampling = obj.get("sampling", "volume")
    if sampling == "surface":
        if not nodes:
            raise ValueError("Surface sampling is for loads/supports; material/domain roles need a closed volume")
        distance = query.compute_implicit_distance(mesh)["implicit_distance"]
        return (np.abs(distance) <= tolerance).reshape(coordinates.shape[:-1])
    if sampling != "volume":
        raise ValueError("STL sampling must be volume or surface")
    if mesh.n_open_edges or not mesh.is_manifold:
        raise ValueError("An STL volume must be closed and manifold; use surface sampling for a support/load patch")
    mesh = mesh.compute_normals(auto_orient_normals=True, consistent_normals=True, split_vertices=False)
    # Signed distance is the documented reliable interior method. Include the
    # boundary explicitly so a surface coincident with a grid plane keeps nodes.
    distance = query.compute_implicit_distance(mesh)["implicit_distance"]
    epsilon = max(mesh.length, 1) * 1e-8
    return (distance <= epsilon).reshape(coordinates.shape[:-1])
