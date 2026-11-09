# plugins/postprocessors/truss_solid.py — a clean solid from a truss: bars, joints, one outline.
#
# A truss design (methods/truss.py) is bars between nodes.  To make it, every bar becomes a
# capsule as wide as its area (2-D, unit thickness: width = a) or a rod of the same
# cross-section (3-D: radius √(a/π)), and every node where bars meet gets a round joint as
# large as its thickest bar (larger for a joint-mass node, plugins/physics/truss_nodes.py).
# The solid is the union of all of them, found from their signed distance field
#
#     φ(p) = min( min_i (d(p, bar_i) − r_i),  min_j (|p − n_j| − R_j) ),     solid where φ ≤ 0,
#
# cut to the design domain (φ ← max(φ, distance outside the domain box), so a thick bar along
# an edge does not stick out), sampled on a fine grid of its own (a few points across the
# thinnest bar, not the finite-element mesh) and traced at φ = 0: marching squares in 2-D (one closed outline per
# boundary, holes included, written as DXF and SVG), marching cubes in 3-D (an STL surface).
# Bars thinner than `min_area` of the thickest are left out, as the optimiser's lower bound
# keeps them only to keep the stiffness matrix solvable.
#
# It runs only when it is in the run's post-processing list, and only on a design that is a
# network; on any other design it reports that and writes nothing.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.postprocess import PostProcessor

from .export_dxf import dxf_text
from .export_stl import write_binary_stl
from .export_svg import svg_text


def _segment_distance(points, a, b):
    """Distance from every point to the segment a-b."""
    ab = b - a
    t = np.clip(((points - a) @ ab) / max(float(ab @ ab), 1e-30), 0.0, 1.0)
    return np.linalg.norm(points - (a + t[:, None] * ab), axis=1)


def signed_distance(points, nodes, bars, radii, joints):
    """φ at `points`: negative inside the union of the bar capsules and the joint balls."""
    phi = np.full(len(points), np.inf)
    for (i, j), r in zip(bars, radii, strict=True):
        a, b = nodes[i], nodes[j]
        low, high = np.minimum(a, b) - r, np.maximum(a, b) + r
        near = np.all((points >= low - 1e-9) & (points <= high + 1e-9), axis=1)
        if near.any():
            phi[near] = np.minimum(phi[near], _segment_distance(points[near], a, b) - r)
    for centre, radius in joints:
        near = np.all(np.abs(points - centre) <= radius + 1e-9, axis=1)
        if near.any():
            phi[near] = np.minimum(phi[near], np.linalg.norm(points[near] - centre, axis=1) - radius)
    return np.where(np.isfinite(phi), phi, 1.0)


def solid_parts(network, dims, min_area=0.05, joint_scale=1.0):
    """The bars kept, their radii, and one joint (centre, radius) per node where kept bars meet."""
    from toporia_library.physics.truss import bar_radius
    nodes = np.asarray(network["nodes"], dtype=float)
    bars = np.asarray(network["bars"], dtype=int).reshape(-1, 2)
    areas = np.asarray(network["areas"], dtype=float)
    keep = areas > min_area * max(float(np.max(areas)), 1e-30)
    bars, radii = bars[keep], bar_radius(areas[keep], dims)
    return nodes, bars, radii, joints_for(nodes, bars, radii, network, joint_scale)


def joints_for(nodes, bars, radii, network, joint_scale=1.0):
    """One joint (centre, radius) per node where the given bars meet: the thickest bar's radius, scaled."""
    largest = np.zeros(len(nodes))
    np.maximum.at(largest, bars[:, 0], radii)
    np.maximum.at(largest, bars[:, 1], radii)
    # A joint with material (truss_nodes.py) is at least the ball that holds its volume.
    own = np.asarray(network.get("joint_radius") or np.zeros(len(nodes)), dtype=float)
    return [(nodes[n], max(largest[n] * joint_scale, own[n])) for n in np.flatnonzero(largest > 0)]


class TrussSolid(PostProcessor):
    """A truss as a clean solid: bar capsules joined by round nodes, as one outline (2-D) or surface (3-D)."""

    name = "truss_solid"
    label = "Truss to a clean solid"
    use_when = ("At the end of a truss run, to make the bars into a shape you can cut, print or take into CAD: "
                "DXF and SVG outlines in 2-D, an STL surface in 3-D.")
    reference = ("Toporia's own construction: union of capsules and joint balls through a signed distance field, "
                 "traced by marching squares/cubes (W. E. Lorensen, H. E. Cline, SIGGRAPH 1987).")
    order = 55
    dims = None
    table_metrics = ("bars", "joints")
    params = (
        Param("min_area", 0.05, "Smallest bar", "Bars thinner than this fraction of the thickest are left out.",
              min=0.0, max=1.0, decimals=4),
        Param("joint_scale", 1.0, "Joint size", "Joint radius relative to the thickest bar meeting there. 0 "
              "leaves the capsule ends as the only rounding.", min=0.0, max=10.0, step=0.1, decimals=2),
        Param("samples", 6, "Detail", "Grid points across the thinnest kept bar; more is smoother and slower.",
              min=2, max=40),
    )

    def __init__(self, min_area=0.05, joint_scale=1.0, samples=6):
        self.min_area, self.joint_scale, self.samples = min_area, joint_scale, int(samples)

    def process(self, result):
        network = getattr(result, "network", None)
        if not network:
            return {"bars": None, "joints": None, "note": "not a truss design"}
        dims = len(network["nodes"][0])
        nodes, bars, radii, joints = solid_parts(network, dims, self.min_area, self.joint_scale)
        if not len(bars):
            return {"bars": 0, "joints": 0}
        reach = max([float(np.max(radii))] + [radius for _, radius in joints])
        low, high = nodes.min(axis=0) - reach * 1.5, nodes.max(axis=0) + reach * 1.5
        coarsest = float(np.max(high - low)) / (900 if dims == 2 else 160)      # the grid's own limit
        # A bar narrower than about one grid step would break into fragments: it is left out
        # (and counted in "too_thin") rather than drawn as dust.
        drawable = radii >= coarsest
        dropped = int(np.count_nonzero(~drawable))
        if dropped:
            bars, radii = bars[drawable], radii[drawable]
            if not len(bars):
                return {"bars": 0, "joints": 0, "too_thin": dropped}
            joints = joints_for(nodes, bars, radii, network, self.joint_scale)
        step = max(2 * float(np.min(radii)) / self.samples, coarsest)
        axes = [np.arange(lo, hi + step, step) for lo, hi in zip(low, high, strict=True)]
        grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1)
        phi = signed_distance(grid.reshape(-1, dims), nodes, bars, radii, joints).reshape(grid.shape[:-1])
        # Cut to the design domain: a thick bar along an edge must not stick out of it.
        problem = result.problem
        extent = np.array([problem.Lx, problem.Ly] + ([problem.Lz] if dims == 3 else []))
        outside = np.max(np.maximum(-grid, grid - extent), axis=-1)       # > 0 outside the box
        phi = np.maximum(phi, outside)
        if dims == 2:
            polygons = self._outlines(phi, axes)
            problem = result.problem
            result.file("truss_solid.dxf").write_text(dxf_text(polygons), encoding="ascii")
            result.file("truss_solid.svg").write_text(
                svg_text(polygons, problem.Lx, problem.Ly, "evenodd"), encoding="utf-8")
            area = float(np.count_nonzero(phi <= 0)) * step ** 2
            return {"bars": int(len(bars)), "joints": len(joints), "outlines": len(polygons), "area": area,
                    "too_thin": dropped}
        triangles = self._surface(phi, axes, step)
        if triangles is None:
            return {"bars": int(len(bars)), "joints": len(joints), "note": "pip install scikit-image for the STL"}
        write_binary_stl(result.file("truss_solid.stl"), triangles)
        volume = float(np.count_nonzero(phi <= 0)) * step ** 3
        return {"bars": int(len(bars)), "joints": len(joints), "triangles": int(len(triangles)), "volume": volume,
                "too_thin": dropped}

    @staticmethod
    def _outlines(phi, axes):
        """Closed polygons (mm) where φ = 0, by marching squares (contourpy, which matplotlib brings)."""
        from contourpy import contour_generator
        x, y = axes
        generator = contour_generator(x, y, phi.T, line_type="Separate")
        polygons = []
        for line in generator.lines(0.0):
            if len(line) >= 4:
                closed = line if np.allclose(line[0], line[-1]) else np.vstack([line, line[:1]])
                polygons.append([tuple(point) for point in closed])
        return polygons

    @staticmethod
    def _surface(phi, axes, step):
        """Triangles (mm) where φ = 0, by marching cubes; None without scikit-image."""
        try:
            from skimage.measure import marching_cubes
        except ImportError:
            return None
        padded = np.pad(phi, 1, constant_values=1.0)                 # closed at the sampling box
        vertices, faces, _, _ = marching_cubes(padded, level=0.0, spacing=(step,) * 3)
        origin = np.array([axis[0] for axis in axes]) - step
        return (vertices + origin)[faces].astype(np.float32)
