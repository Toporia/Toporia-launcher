# plugins/postprocessors/_measure.py — measurements and drawings several post-processors share.

import numpy as np
from PIL import Image

from toporia.framework.problem.mesh import projection

#: The referee measures every design with the same physics: Q4, SIMP with this penalty, no filter.
REFEREE_PENAL = 3.0


def referee_compliance(problem, density):
    """Compliance of a design measured the same way whatever made it.

    Toporia's Q4 solver (H8 in 3-D), SIMP with p = REFEREE_PENAL, no filter,
    the scenario's load cases and weights; the density is clipped to the
    problem's bounds so holes stay holes.  For a black-and-white design the
    penalty does not matter.
    """
    from toporia.plugins.interpolations.simp import SIMP
    from toporia.plugins.physics.h8_solid import H8Solid
    from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
    engine = H8Solid() if getattr(problem, "dims", 2) == 3 else Q4PlaneStress()
    engine.initialize(problem, {"linear_solver": "auto", "amg_above": 60000, "amg_tol": 1e-8}
                      if getattr(problem, "dims", 2) == 3 else {}, SIMP(REFEREE_PENAL))
    state = engine.solve(np.clip(density, problem.lower_bound, problem.upper_bound))
    return float(sum(weight * engine.compliance(state, case) for case, weight in enumerate(state.weights)))


def grey_level(density):
    """Sigmund's measure of non-discreteness, 4/n Σ ρ(1 − ρ): 0 is black and white, 1 uniform grey."""
    return float(4.0 * np.mean(density * (1.0 - density)))


def element_size(problem):
    """The smallest element edge, in mm."""
    return min(problem.dx, problem.dy, getattr(problem, "dz", problem.dx))


def pinned(problem):
    """Elements whose density is fixed by the problem (holes, solid rings)."""
    return problem.upper_bound <= problem.lower_bound


def save_image(field, path):
    """A design as a greyscale PNG, solid dark, drawn the way final_density.png is (3-D: depth average)."""
    pixels = (np.clip(np.flipud(1.0 - projection(np.asarray(field, dtype=float))), 0.0, 1.0) * 255).astype(np.uint8)
    Image.fromarray(pixels, mode="L").save(path)


def outlines(result):
    """The design's boundary as closed polygons [(n, 2) arrays, in mm, y up].

    The density (clipped to the bounds) is contoured at the level the
    black-and-white design is cut at, on the element centres, with a ring of
    void half an element outside the domain so every outline closes on the
    domain's edge.
    """
    import contourpy
    problem = result.problem
    field = np.clip(result.density, problem.lower_bound, problem.upper_bound)
    padded = np.pad(field, 1, constant_values=0.0)
    x = np.concatenate([[-0.5 * problem.dx], problem.elem_x[0], [problem.Lx + 0.5 * problem.dx]])
    y = np.concatenate([[-0.5 * problem.dy], problem.elem_y[:, 0], [problem.Ly + 0.5 * problem.dy]])
    lines = contourpy.contour_generator(x, y, padded, line_type="Separate").lines(result.level)
    polygons = []
    for line in lines:
        line = np.asarray(line, dtype=float)
        if len(line) < 4:
            continue
        line[:, 0] = np.clip(line[:, 0], 0.0, problem.Lx)
        line[:, 1] = np.clip(line[:, 1], 0.0, problem.Ly)
        polygons.append(line if np.allclose(line[0], line[-1]) else np.vstack([line, line[:1]]))
    return polygons


def polygon_area(polygon):
    """Signed area of a closed polygon (shoelace)."""
    x, y = np.asarray(polygon, dtype=float).T
    return 0.5 * float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))


def clip_to_box(polygon, width, height):
    """A closed polygon cut to the rectangle [0, width] x [0, height] (Sutherland-Hodgman); None if nothing is left."""
    points = [tuple(p) for p in np.asarray(polygon, dtype=float)[:-1]]
    edges = ((0, 0.0, 1), (0, width, -1), (1, 0.0, 1), (1, height, -1))   # (axis, bound, side kept)
    for axis, bound, side in edges:
        if not points:
            return None
        kept = []
        for i, current in enumerate(points):
            previous = points[i - 1]
            inside_now = side * (current[axis] - bound) >= 0
            inside_before = side * (previous[axis] - bound) >= 0
            if inside_now != inside_before:
                t = (bound - previous[axis]) / (current[axis] - previous[axis])
                kept.append(tuple(previous[k] + t * (current[k] - previous[k]) for k in (0, 1)))
            if inside_now:
                kept.append(current)
        points = kept
    if len(points) < 3:
        return None
    polygon = np.array(points + points[:1])
    return polygon if abs(polygon_area(polygon)) > 1e-12 else None


def drawing(result, source):
    """The polygons an outline exporter writes, and which they are: "geometry" or "contour".

    Explicit geometry is cut to the domain and turned counter-clockwise, so
    overlapping shapes fill as their union (non-zero rule); a contour keeps
    its holes as separate outlines (even-odd rule).
    """
    if source == "geometry" or (source == "auto" and result.geometry):
        if not result.geometry:
            raise ValueError("this design has no explicit geometry (only moving morphable components do); "
                             "use source = contour")
        problem = result.problem
        shapes = []
        for polygon in result.geometry:
            cut = clip_to_box(polygon, problem.Lx, problem.Ly)
            if cut is not None:
                shapes.append(cut if polygon_area(cut) > 0 else cut[::-1])
        return shapes, "geometry"
    return outlines(result), "contour"
