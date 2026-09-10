# config.py — all tunable parameters for the optimisation, in one place
#
# Rather than scattering numbers throughout the code, every setting lives here
# as a Python dataclass.  A dataclass is like a C struct: it is just a named
# container for data.  The @dataclass decorator auto-generates __init__ so you
# don't have to write it manually.
#
# Usage pattern:
#   cfg = TopOptConfig(volfrac=0.3, max_iter=200)   ← only override what you need
#   new = dataclasses.replace(cfg, volfrac=0.4)     ← get a modified COPY; original unchanged

import re
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

from .params import Param

# Resolved once at import time so every file can find the project root regardless
# of where the terminal is opened.  __file__ = path of this file.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class LoadCase:
    """One loading scenario: a force vector applied to the load holes.

    Multiple load cases can be combined; each carries a weight so the total
    compliance is the weighted sum:  C = Σ weight_k × C_k.
    Weights should sum to 1 so the objective scale stays consistent.
    """
    Fmag:   float = 1.0   # force magnitude [N or normalised units]
    Fa:     float = 0.0   # force direction in degrees: 0=+x, 90=+y, 180=-x, 270=-y
    weight: float = 1.0   # contribution to the weighted compliance sum


@dataclass
class HoleConfig:
    """Geometric definition of one circular hole in the bracket domain.

    Each hole has two radii:
      r_void    — elements inside this radius are forced to void (the actual hole)
      r_passive — annular ring between r_void and r_passive is forced to solid
                  (the material ring around the bolt hole that must not be removed)

    kind controls the boundary condition applied to nodes inside r_passive:
      "fixed"  → constrained in all DOFs (mounting holes bolted to the frame)
      "load"   → force is distributed over nodes here (motor attachment holes)
      "free"   → geometry only; no structural boundary condition
    """
    cx: float           # hole centre x [mm] from lower-left corner
    cy: float           # hole centre y [mm] from lower-left corner
    r_void:    float    # inner radius: forced void
    r_passive: float    # outer radius: forced solid (> r_void)
    kind: str = "free"


@dataclass
class EnforcedArea:
    """Polygonal area that is forced to stay full or empty during optimisation.

    points: list of (x, y) coordinates in mm, measured from the bottom-left
            domain origin. At least three points are required.
    kind:   "full"  -> elements inside the polygon are forced to density 1
            "empty" -> elements inside the polygon are forced to density 0
    """
    points: list[tuple[float, float]]
    kind: str


@dataclass
class EdgeConstraint:
    """Fix displacement DOFs along an entire domain edge.

    edge: which boundary to constrain — "left", "right", "top", "bottom"
    dof:  which displacement components to fix —
            "x"    fix only the x-displacement (e.g. symmetry plane: no horizontal movement)
            "y"    fix only the y-displacement (e.g. roller support: no vertical movement)
            "both" clamp both DOFs (fully fixed wall)
    """
    edge: str
    dof:  str = "both"


@dataclass
class PointConstraint:
    """Fix displacement DOFs at a specific location (snapped to the nearest mesh node).

    x, y: physical coordinates [mm] measured from the lower-left corner of the domain
    dof:  "x", "y", or "both"  (same meaning as in EdgeConstraint)
    """
    x:   float
    y:   float
    dof: str = "both"


@dataclass
class PointLoad:
    """Mark a specific location as a force application point.

    The force magnitude and direction are taken from the load_cases list — this
    class only records WHERE the force acts.  The nearest mesh node is used.

    x, y: physical coordinates [mm] measured from the lower-left corner of the domain
    """
    x: float
    y: float


@dataclass
class TopOptConfig:
    """Master configuration object — passed to every major function.

    Edit the defaults here, or override individual fields when constructing:
        cfg = TopOptConfig(volfrac=0.3, method="levelset")

    These defaults are intentionally generic. Named geometries such as the
    drone arm belong in the configurations package.
    """

    # ── Algorithm ─────────────────────────────────────────────────────────────
    # Name of a registered method (see toporia.library.methods.METHODS), e.g.
    # "density", "density_mma", "levelset" or "pymoto".
    method: str = "density"

    # The selected method's own parameters, keyed by Param name.  Anything left
    # out uses the default declared on the method class; an unknown key is an
    # error.  Example: {"penal": 3.5, "move": 0.1}
    method_params: dict = field(default_factory=dict)

    # ── Domain geometry [mm] ──────────────────────────────────────────────────
    Lx: float = 100.0   # domain width
    Ly: float = 50.0    # domain height

    # ── Mesh resolution ───────────────────────────────────────────────────────
    # Number of elements = round(Lx*m) × round(Ly*m).
    # m=1 → 200×85 mesh.  m=2 → 400×170.  Higher = sharper result but slower.
    m: float = 1.0

    # ── Hole geometry ─────────────────────────────────────────────────────────
    # Problem presets should fill this list in topopt_simple/configurations/.
    # Keep the core default empty so TopOptConfig() does not imply a drone arm.
    # field(default_factory=...) is required because mutable defaults (lists)
    # must not be shared between instances — each instance gets its own copy.
    holes: list[HoleConfig] = field(default_factory=list)

    # Polygonal regions with prescribed material state. These are rasterised on
    # element centres in BracketProblem and merged into passive/void masks.
    enforced_areas: list[EnforcedArea] = field(default_factory=list)

    # ── Edge and point boundary conditions ────────────────────────────────────
    # Alternative to hole-based BCs: define constraints and load points directly
    # on edges or at arbitrary coordinates.  Both systems can be mixed — a config
    # can use holes for geometry and edge/point entries for the structural BCs.
    edge_constraints:  list[EdgeConstraint]  = field(default_factory=list)
    point_constraints: list[PointConstraint] = field(default_factory=list)
    point_loads:       list[PointLoad]       = field(default_factory=list)

    # ── Load cases ────────────────────────────────────────────────────────────
    load_cases: list[LoadCase] = field(
        default_factory=lambda: [LoadCase(Fmag=1.0, Fa=0.0, weight=1.0)]
    )

    # ── Design constraint and convergence ─────────────────────────────────────
    volfrac: float = 0.5    # target fraction of solid material (0=all void, 1=all solid)
    max_iter: int  = 100    # hard iteration limit
    tol:     float = 0.01   # stop when the design change a method reports is below tol

    # ── Filter pipeline ───────────────────────────────────────────────────────
    # Filters applied in order, each {"type": <filter name>, <param>: <value>}.
    # Types and their parameters are declared on the filter classes (see
    # toporia.library.methods.filters.FILTERS); omitted parameters use defaults.
    # Only honoured by methods whose capabilities say accepts_filters=True.
    # Empty list means raw optimiser output with no filtering.
    # Example: [{"type": "density", "rmin": 2.0}, {"type": "symmetry", "axis": "left_right"}]
    filter_specs: list = field(default_factory=lambda: [{"type": "density"}])

    # ── Material properties (linear elastic) ─────────────────────────────────
    E0:   float = 1.0    # Young's modulus of solid material (normalised)
    Emin: float = 1e-9   # tiny stiffness for void elements (avoids singular K matrix)
    nu:   float = 0.3    # Poisson's ratio

    # ── Output ────────────────────────────────────────────────────────────────
    output_dir: Path = PROJECT_ROOT / "results"
    save_every: int  = 10   # save intermediate density PNG every N iterations (0 = off)


# ── Parameter declarations for the scenario-level fields ──────────────────────
# Method and filter parameters are declared on their own classes in
# toporia.library.  These are the fields every run has, whatever its method.
# The GUI builds its Core / Convergence / Output panels from them.

DESIGN_PARAMS = (
    Param("m", 1.0, "Mesh res m",
          "Elements per millimetre. Higher values give finer designs but slower FEA.",
          min=0.1, max=5.0, step=0.1, decimals=2, units="el/mm"),
    Param("volfrac", 0.5, "Vol fraction",
          "Target fraction of solid material allowed in the design.",
          min=0.01, max=1.0, step=0.05, decimals=3),
)
CONVERGENCE_PARAMS = (
    Param("max_iter", 100, "Max iters",
          "Maximum number of optimisation iterations before stopping.", min=1, max=2000),
    Param("tol", 0.01, "Tolerance",
          "Stop when the design change reported by the method falls below this value.",
          min=0.0, max=1.0, step=0.005, decimals=4),
)
OUTPUT_PARAMS = (
    Param("save_every", 10, "Save every N",
          "Save an intermediate density image every N iterations. Use 0 for final only.",
          min=0, max=1000),
)
CONFIG_PARAMS = DESIGN_PARAMS + CONVERGENCE_PARAMS + OUTPUT_PARAMS


_INDEXED_PATH = re.compile(r"^(?P<collection>\w+)\[(?P<index>\d+)\]\.(?P<field>\w+)$")


def apply_param(cfg, path: str, value):
    """Return a NEW config with the value at one parameter path replaced.

    Parameter paths
    ---------------
      "volfrac"              a TopOptConfig field
      "method.penal"         a parameter of the selected method (config.method_params)
      "filters[1].beta"      a parameter of the second filter in config.filter_specs
      "load_cases[0].Fmag"   a field of the first load case

    Method and filter parameter names are not checked here, because core does
    not know which plugins exist.  They are validated when the run starts,
    against the Param declarations on the plugin classes, so a typo still fails
    before any computation.  toporia.library.catalog.parameter_paths lists the
    valid paths for a given configuration.

    The original cfg is never modified: sweeps rely on the base config staying
    unchanged across every cell.
    """
    if path.startswith("method."):
        name = path[len("method."):]
        return replace(cfg, method_params={**cfg.method_params, name: value})

    match = _INDEXED_PATH.match(path)
    if match:
        collection, index, field_name = match["collection"], int(match["index"]), match["field"]
        if collection == "filters":
            specs = [dict(spec) for spec in cfg.filter_specs]
            specs[index][field_name] = value
            return replace(cfg, filter_specs=specs)
        if collection == "load_cases":
            cases = list(cfg.load_cases)
            cases[index] = replace(cases[index], **{field_name: value})
            return replace(cfg, load_cases=cases)
        raise KeyError(f"Unknown parameter collection {collection!r} in path {path!r}")

    fields_by_name = {f.name: f for f in fields(cfg)}
    if path not in fields_by_name:
        raise KeyError(f"Unknown parameter path {path!r}")
    if fields_by_name[path].type in (int, "int"):
        value = int(round(value))   # sweeps generate floats; keep integer fields integral
    return replace(cfg, **{path: value})
