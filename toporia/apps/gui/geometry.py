# apps/gui/geometry.py — editor objects in physical coordinates, independent of pixels/mesh.
# Each shape has an identity, transform and physical role. The solver adapter
# consumes these definitions; the viewport and inspector never own numerical state.

import math
from uuid import uuid4


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
        objects.append(make_object("circle", pos, (2 * hole.r_passive,) * 3, "solid"))
        objects.append(make_object("circle", pos, (2 * hole.r_void,) * 3, "void"))
        if hole.kind == "fixed":
            objects.append(make_object("circle", pos, (2 * hole.r_passive,) * 3, "support"))
    for area in scenario.enforced_areas:
        objects.append(make_object("polygon", role="solid" if area.kind == "full" else "void",
                                   vertices=[list(p) for p in area.points]))
    for case_index, case in enumerate(scenario.load_cases):
        angle, elevation = math.radians(case.Fa), math.radians(case.Fe)
        force = [case.Fmag * math.cos(elevation) * math.cos(angle),
                 case.Fmag * math.cos(elevation) * math.sin(angle), case.Fmag * math.sin(elevation)]
        for x, y in loads:
            objects.append(make_object(position=(x, y, 0), role="load", force=force, case=case_index))
    return objects
