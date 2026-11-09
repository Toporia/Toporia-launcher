# apps/gui/geometry.py — editor objects in physical coordinates, independent of pixels/mesh.
# Each shape has an identity, transform and physical role. The solver adapter
# consumes these definitions; the viewport and inspector never own numerical state.

import math
from uuid import uuid4

#: One colour per physical role, shared by the 2-D and the 3-D editor.
COLOURS = {"support": "#49a5db", "load": "#f87777", "solid": "#c2cad3", "void": "#e1bc66", "domain": "#82cfa0",
           "spring": "#a77bd6", "port": "#f0a35e", "heat_loss": "#e86fae"}


def snap(value, step):
    """`value` on the nearest multiple of `step`; unchanged when step is 0 or None."""
    return round(value / step) * step if step else value


def box_from_corners(first, second, z, height, step=None, minimum=None):
    """An axis-aligned box drawn on the work plane at height `z`: footprint from two corners.

    Coordinates snap to `step` mm when given; a side never collapses below `minimum`
    (one snap step, or 1 % of the larger side).
    """
    (x0, y0), (x1, y1) = (snap(v, step) for v in first[:2]), (snap(v, step) for v in second[:2])
    low = [min(x0, x1), min(y0, y1), snap(z, step)]
    size = [abs(x1 - x0), abs(y1 - y0), snap(height, step) or height]
    floor = minimum or step or 0.01 * max(size[0], size[1], height, 1e-9)
    size = [max(s, floor) for s in size]
    return low, size


def resizable(obj):
    """True for an object a box widget can move and resize: an unrotated box."""
    return obj.get("shape") == "box" and not any(obj.get("rotation", [0, 0, 0])) and not obj.get("extrusion")


def object_from_bounds(obj, bounds, step=None):
    """A box object moved and resized to (xmin, xmax, ymin, ymax, zmin, zmax), snapped to `step`."""
    import copy
    edited = copy.deepcopy(obj)
    low = [snap(bounds[0], step), snap(bounds[2], step), snap(bounds[4], step)]
    high = [snap(bounds[1], step), snap(bounds[3], step), snap(bounds[5], step)]
    floor = step or 1e-6
    edited["position"] = low
    edited["size"] = [max(h - lo, floor) for lo, h in zip(low, high, strict=True)]
    return edited


def make_object(shape="point", position=(0.0, 0.0, 0.0), size=(1.0, 1.0, 1.0), role="support", **values):
    """Create a serializable object with a stable identity and explicit physical role."""
    return {"id": uuid4().hex, "name": f"{role.title()} {shape}", "shape": shape,
            "position": list(position), "size": list(size), "rotation": [0.0, 0.0, 0.0],
            "role": role, "axes": ["x", "y"], "force": [0.0, -1.0, 0.0], "case": 0, **values}


def objects_from_scenario(scenario):
    """Make explicit editable objects from legacy presets, including their fallbacks."""
    from .preview import supports_and_loads
    edges, points, loads = supports_and_loads(scenario)
    objects = []
    for edge, dof in edges:
        start, size = {
            "left": ((0, 0, 0), (0, scenario.Ly, 0)),
            "right": ((scenario.Lx, 0, 0), (0, scenario.Ly, 0)),
            "bottom": ((0, 0, 0), (scenario.Lx, 0, 0)),
            "top": ((0, scenario.Ly, 0), (scenario.Lx, 0, 0)),
        }[edge]
        objects.append(make_object("line", start, size, axes=["x", "y"] if dof == "both" else [dof]))
    for x, y, dof in points:
        objects.append(make_object(position=(x, y, 0), axes=["x", "y"] if dof == "both" else [dof]))
    for hole in scenario.holes:
        pos = (hole.cx, hole.cy, 0)
        # A ring without a hole (r_void = 0) is a solid disc; a hole without a ring has no solid.
        if hole.r_passive > hole.r_void:
            objects.append(make_object("circle", pos, (2 * hole.r_passive,) * 3, "solid", inner_radius=hole.r_void))
        if hole.r_void > 0:
            objects.append(make_object("circle", pos, (2 * hole.r_void,) * 3, "void"))
        if hole.kind == "fixed":
            objects.append(make_object("circle", pos, (2 * hole.r_passive,) * 3, "support"))
    for area in scenario.enforced_areas:
        objects.append(make_object("polygon", role="solid" if area.kind == "full" else "void",
                                   vertices=[list(p) for p in area.points]))
    # A load hole is loaded on its solid ring (its centre is empty); every other load is a point.
    rings = [hole for hole in scenario.holes if hole.kind == "load"]
    centres = {(hole.cx, hole.cy) for hole in rings}
    for case_index, case in enumerate(scenario.load_cases):
        if case.Fmag == 0:      # e.g. heat generated in the material only: nothing enters at a point
            continue
        angle, elevation = math.radians(case.Fa), math.radians(case.Fe)
        force = [case.Fmag * math.cos(elevation) * math.cos(angle),
                 case.Fmag * math.cos(elevation) * math.sin(angle), case.Fmag * math.sin(elevation)]
        for x, y in loads:
            if (x, y) not in centres:
                objects.append(make_object(position=(x, y, 0), role="load", force=force, case=case_index))
        for hole in rings:
            objects.append(make_object("circle", (hole.cx, hole.cy, 0), (2 * hole.r_passive,) * 3, "load",
                                       force=force, case=case_index))
    # Ground springs and a mechanism's output port become objects of their own (regions.py).
    for spring in scenario.point_springs:
        if spring.stiffness > 0:
            objects.append(make_object(position=(spring.x, spring.y, 0), role="spring", axes=[spring.dof],
                                       stiffness=spring.stiffness, name=f"Spring {spring.dof}"))
    if scenario.objective.get("type") == "output_displacement":
        objective = scenario.objective
        objects.append(make_object(position=(objective.get("x", 60.0), objective.get("y", 10.0), 0), role="port",
                                   direction=objective.get("angle", 180.0), name="Output port"))
    if scenario.Lz > 0:
        for obj in objects:
            obj["extrusion"] = scenario.Lz
            if obj["role"] == "support" and "z" not in obj["axes"]:
                obj["axes"].append("z")
    return objects
