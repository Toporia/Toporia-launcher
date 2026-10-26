# framework/problem/regions.py — explicit physical regions to structured-mesh masks.
#
# This adapter is shared by GUI and CLI. It never invents supports or loads.
# Regional forces are total vectors, distributed equally across selected nodes;
# every load owns its own vector and load case. Legacy presets bypass this file.

import math

import numpy as np


def validate_scenario(scenario, m):
    """Reject invalid dimensions/material before allocating mesh arrays."""
    values = [scenario.Lx, scenario.Ly, scenario.Lz, scenario.E0, scenario.Emin, scenario.nu, m]
    if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values):
        raise ValueError("Domain, material and resolution must be finite numbers")
    if min(scenario.Lx, scenario.Ly, m, scenario.E0, scenario.Emin) <= 0 or scenario.Lz < 0:
        raise ValueError("Domain size, resolution and stiffness must be positive")
    if not -1 < scenario.nu < .5:
        raise ValueError("Poisson ratio must lie between -1 and 0.5")
    counts = [round(scenario.Lx * m), round(scenario.Ly * m)]
    if scenario.Lz:
        counts.append(round(scenario.Lz * m))
    if min(counts) < 1:
        raise ValueError("Resolution gives zero elements along an axis; increase the resolution")
    if math.prod(counts) > 2_000_000:
        raise ValueError("This editor limits a mesh to 2,000,000 elements; reduce resolution before running")


def _coordinates(problem, nodes):
    prefix = "node" if nodes else "elem"
    return np.stack([getattr(problem, f"{prefix}_{axis}") for axis in "xyz"[:problem.dims]], axis=-1)


def region_mask(obj, coordinates, tolerance, nodes=False):
    """Sample one transformed shape at physical node or element-centre coordinates."""
    dims = coordinates.shape[-1]
    position = np.asarray(obj["position"], dtype=float)[:dims]
    size = np.asarray(obj["size"], dtype=float)[:dims]
    local = coordinates - position
    angle = np.deg2rad(obj.get("rotation", [0, 0, 0])[2])
    c, s = np.cos(angle), np.sin(angle)
    local = local.copy()
    local[..., 0], local[..., 1] = c * local[..., 0] + s * local[..., 1], -s * local[..., 0] + c * local[..., 1]
    shape = obj["shape"]
    eps = 1e-8
    if dims != 2:
        raise ValueError("Spatial region meshing is not available yet; use a 2D custom problem")
    if shape == "point":
        dist = np.linalg.norm(local, axis=-1)
        mask = np.zeros(dist.shape, dtype=bool)
        mask.flat[np.argmin(dist)] = True
        if not nodes:
            raise ValueError("A point cannot define a material/domain region; use an area")
        if dist.min() > tolerance * 1.5:
            raise ValueError(f"{obj['name']}: point lies outside the domain")
        return mask
    if shape == "line":
        if not nodes:
            raise ValueError("A line cannot define a material/domain region; use an area")
        length2 = np.dot(size, size)
        if length2 <= 0:
            raise ValueError(f"{obj['name']}: line needs distinct endpoints")
        fraction = np.clip(np.sum(local * size, axis=-1) / length2, 0, 1)
        return np.linalg.norm(local - fraction[..., None] * size, axis=-1) <= tolerance
    if shape == "rectangle":
        if np.any(size <= 0):
            raise ValueError(f"{obj['name']}: rectangle dimensions must be positive")
        return np.all((local >= -eps) & (local <= size + eps), axis=-1)
    if shape == "circle":
        if np.any(size <= 0):
            raise ValueError(f"{obj['name']}: circle diameters must be positive")
        mask = np.sum((local / (size / 2)) ** 2, axis=-1) <= 1 + eps
        if obj.get("inner_radius", 0):
            mask &= np.linalg.norm(local, axis=-1) > obj["inner_radius"]
        return mask
    if shape == "polygon":
        points = np.asarray(obj.get("vertices", []), dtype=float)
        if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] != 2:
            raise ValueError("A polygon needs at least three XY vertices")
        x, y = local[..., 0], local[..., 1]
        mask = np.zeros(x.shape, dtype=bool)
        xj, yj = points[-1]
        for xi, yi in points:
            mask ^= ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi + 1e-300) + xi)
            xj, yj = xi, yi
        return mask
    raise ValueError(f"Unsupported region shape: {shape!r}")


def validate_object(obj, dims):
    """Validate physical object data before using it in geometry or physics."""
    if not isinstance(obj, dict):
        raise ValueError("Every region must be an object")
    for key in ("position", "size", "rotation", "force"):
        value = obj.get(key)
        if not isinstance(value, list) or len(value) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in value):
            raise ValueError(f"Region {key} must contain three finite numbers")
    if obj.get("role") not in {"domain", "support", "load", "solid", "void"}:
        raise ValueError("Region role must be domain, support, load, solid or void")
    if obj.get("role") == "support" and (not obj.get("axes") or set(obj["axes"]) - set("xyz"[:dims])):
        raise ValueError(f"{obj.get('name', 'Support')}: select at least one supported displacement axis")
    if obj.get("role") == "load":
        if type(obj.get("case")) is not int or obj["case"] < 0:
            raise ValueError("A load case index must be a nonnegative integer")
        if not np.any(obj["force"]):
            raise ValueError(f"{obj.get('name', 'Load')}: force must be nonzero")
        if dims == 2 and obj["force"][2] != 0:
            raise ValueError("A 2D problem cannot carry an out-of-plane force")


def apply_regions(problem):
    """Replace legacy masks with explicit geometry and validate supports and loads."""
    objects = problem.scenario.regions
    node_coords, elem_coords = _coordinates(problem, True), _coordinates(problem, False)
    for name in ("void_elements", "passive_elements", "fixed_nodes", "fixed_x_nodes", "fixed_y_nodes", "load_nodes"):
        getattr(problem, name).fill(False)
    if problem.dims == 3:
        problem.fixed_z_nodes.fill(False)
    problem.load_node_sets = []
    problem.region_loads = []
    domain = np.zeros(problem.shape, bool)
    has_domain = False
    tolerance = .51 * np.linalg.norm([problem.dx, problem.dy])
    for obj in objects:
        validate_object(obj, problem.dims)
        role = obj["role"]
        nodes = role in {"support", "load"}
        mask = region_mask(obj, node_coords if nodes else elem_coords, tolerance, nodes)
        if not np.any(mask):
            raise ValueError(f"{obj.get('name', role)} selects no {'nodes' if nodes else 'elements'}; refine the mesh or enlarge the region")
        if role == "domain":
            domain |= mask
            has_domain = True
        elif role in {"solid", "void"}:
            target = problem.passive_elements if role == "solid" else problem.void_elements
            target |= mask
        elif role == "support":
            for axis in obj["axes"]:
                getattr(problem, f"fixed_{axis}_nodes")[:] |= mask
        elif role == "load":
            if obj["case"] >= len(problem.scenario.load_cases):
                raise ValueError(f"{obj['name']}: load case {obj['case'] + 1} does not exist; add it under Load Cases")
            problem.load_nodes |= mask
            problem.load_node_sets.append(mask)
            problem.region_loads.append((obj["case"], mask, np.asarray(obj["force"][:problem.dims])))
    if has_domain:
        problem.void_elements |= ~domain
    if np.any(problem.void_elements & problem.passive_elements):
        raise ValueError("Solid and void/domain regions conflict on at least one element")
    if np.all(problem.void_elements):
        raise ValueError("No designable elements remain in the domain")
    if problem.passive_elements.mean() > problem.scenario.volfrac + 1e-9:
        raise ValueError("Forced solid material exceeds the material budget")
    # A load/support in removed material must not act through the artificial
    # residual stiffness used to regularise void elements.
    active_nodes = np.zeros(problem.node_x.shape, bool)
    import itertools
    for offsets in itertools.product((0, 1), repeat=problem.dims):
        slices = tuple(slice(offset, offset + size) for offset, size in zip(offsets, problem.shape, strict=True))
        active_nodes[slices] |= ~problem.void_elements
    for axis in "xyz"[:problem.dims]:
        getattr(problem, f"fixed_{axis}_nodes")[:] &= active_nodes
    for _, mask, _ in problem.region_loads:
        mask &= active_nodes
        if not np.any(mask):
            raise ValueError("A load region lies entirely in excluded material")
    validate_supports(problem, node_coords)
    if not problem.region_loads:
        raise ValueError("Add at least one load object; custom problems have no implicit loads")
    cases = problem.scenario.load_cases
    if not cases or any(not math.isfinite(c.weight) or c.weight <= 0 for c in cases):
        raise ValueError("Every load case needs a positive finite weight")
    present = {index for index, _, _ in problem.region_loads}
    if present != set(range(len(cases))):
        raise ValueError("Every load case needs at least one load object")
    node_ids = np.arange(problem.nn).reshape(problem.node_x.shape)
    for index in range(len(cases)):
        force = regional_force(problem, node_ids, problem.dims, index).reshape(-1, problem.dims)
        for axis, name in enumerate("xyz"[:problem.dims]):
            force[(problem.fixed_nodes | getattr(problem, f"fixed_{name}_nodes")).ravel(), axis] = 0
        if not np.any(force):
            raise ValueError(f"Load case {index + 1} has no force on free displacement components")
    problem.validate()


def validate_supports(problem, coordinates):
    """Check that prescribed components remove rigid-body translations and rotations."""
    dims = problem.dims
    coords = coordinates / max(problem.Lx, problem.Ly, getattr(problem, "Lz", 0), 1)
    rows = []
    for axis in range(dims):
        mask = problem.fixed_nodes | getattr(problem, f"fixed_{'xyz'[axis]}_nodes")
        xyz = coords[mask]
        for point in xyz:
            if dims == 2:
                x, y = point
                rows.append([1, 0, -y] if axis == 0 else [0, 1, x])
            else:
                x, y, z = point
                rows.append(([1, 0, 0, 0, z, -y], [0, 1, 0, -z, 0, x], [0, 0, 1, y, -x, 0])[axis])
    required = 3 if dims == 2 else 6
    rank = np.linalg.matrix_rank(rows) if rows else 0
    if rank < required:
        raise ValueError(f"Insufficient supports: {required - rank} rigid-body mode(s) remain; add or adjust supports")


def regional_force(problem, node_ids, dims, case_index):
    """Map total regional forces into any solver's node-numbering convention."""
    force = np.zeros(dims * problem.nn)
    for index, mask, vector in problem.region_loads:
        if index != case_index:
            continue
        ids = node_ids[mask]
        for axis in range(dims):
            np.add.at(force, dims * ids + axis, vector[axis] / len(ids))
    return force
