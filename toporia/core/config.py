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

from dataclasses import dataclass, field
from pathlib import Path

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
    # "density"  → SIMP density method (top88): robust, widely used, recommended
    # "levelset" → RBF level-set method (TOPRBF): crisp boundaries, slower
    method: str = "density"

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

    # ── Density method (SIMP) parameters ─────────────────────────────────────
    volfrac: float = 0.5    # target fraction of solid material (0=all void, 1=all solid)
    penal:   float = 3.0    # SIMP penalty: pushes intermediate densities toward 0 or 1
    rmin:    float = 1.5    # default filter radius [elements]
    max_iter: int  = 100    # hard iteration limit
    tol:     float = 0.01   # convergence: stop when max density change < tol
    move:    float = 0.20   # OC update step limit: max density change per iteration
    mma_tol: float = 1e-4   # MMA convergence tolerance on max design-variable change
    mma_asyinit: float = 0.5  # initial MMA asymptote distance as fraction of bounds
    mma_asyincr: float = 1.2  # asymptote expansion after consistent design motion
    mma_asydecr: float = 0.7  # asymptote contraction after oscillating design motion
    mma_c: float = 1000.0     # upper multiplier scale for the one-constraint MMA solve

    # ── Filter pipeline ───────────────────────────────────────────────────────
    # List of filter spec dicts applied in order: Regularization → Projection → Manufacturing.
    # Each dict must have "type" in {"density","sensitivity","heaviside","am","routing","symmetry"} plus
    # type-specific params.  See methods/filters.py for full parameter reference.
    # Empty list means raw optimizer output with no filtering.
    # Example: [{"type":"density"},{"type":"symmetry","axis":"left_right"},{"type":"routing","radius_mm":2.0,"start_iter":20}]
    filter_specs: list = field(default_factory=lambda: [{"type": "density"}])

    # ── Material properties (linear elastic) ─────────────────────────────────
    E0:   float = 1.0    # Young's modulus of solid material (normalised)
    Emin: float = 1e-9   # tiny stiffness for void elements (avoids singular K matrix)
    nu:   float = 0.3    # Poisson's ratio

    # ── Level-set method parameters ───────────────────────────────────────────
    # Evolution and volume-control parameters from TOPRBF.m.
    ls_dt:         float = 0.5    # level-set update step; larger is faster, smaller is steadier
    ls_nrelax:     int   = 30     # ramp iterations before feedback volume control starts
    ls_delta:      float = 10.0   # half-width of the Phi=0 delta band that receives updates
    ls_mu:         float = 20.0   # relaxation-phase volume penalty strength
    ls_gamma:      float = 0.05   # initial feedback gain after relaxation
    ls_gamma_step: float = 0.05   # feedback gain increase per iteration
    ls_gamma_max:  float = 5.0    # feedback gain cap to limit oscillation

    # RBF initialization and numerical-resolution controls.
    ls_init_hole_radius: float = 0.1   # initial hole radius as a fraction of nely
    ls_rbf_c:            float = 1e-4  # multiquadric RBF regularization constant
    ls_sample_step:      float = 0.1   # element-volume sampling spacing in [-1, 1]
    ls_max_nodes:        int   = 3000  # dense RBF node cap before coarsening internally

    # ── Output ────────────────────────────────────────────────────────────────
    output_dir: Path = PROJECT_ROOT / "results"
    save_every: int  = 10   # save intermediate density PNG every N iterations (0 = off)


def apply_param(cfg, key: str, value: float):
    """Return a NEW config with exactly one parameter changed.
    is used in the GUI to number load case parameters The "lc" prefix
    Handles two key formats:
      "volfrac"   → plain TopOptConfig field
      "lc0.Fmag"  → sub-field of load case 0 (index after "lc", field after ".")

    The original cfg is never modified — dataclasses.replace() always makes a copy.
    This immutability is important in sweep loops where the base config must stay
    unchanged across all iterations.
    """
    from dataclasses import replace
    if key.startswith("lc") and "." in key:
        dot   = key.index(".")
        idx   = int(key[2:dot])      # extract integer index from "lc0", "lc1", etc.
        field = key[dot + 1:]        # field name after the dot: "Fmag", "Fa", or "weight"
        cases = list(cfg.load_cases) # copy the list so we can replace one element
        cases[idx] = replace(cases[idx], **{field: value})  # replace that load case
        return replace(cfg, load_cases=cases)
    return replace(cfg, **{key: value})  # plain field: replace directly
