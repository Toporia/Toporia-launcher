# framework/problem/scenario.py — WHAT is being solved.
#
# A Scenario is the physical problem: the design domain, where the part is held,
# where and how it is loaded, what it is made of, and how much material it may
# use.  It says nothing about how the problem is solved — that is the Solver
# (framework/problem/solver.py) — so the same scenario can be handed to any method, at any
# mesh resolution, and the results compared.
#
# Scenarios are plain data and round-trip through JSON (framework/problem/files.py).
# Coordinates are in mm, measured from the bottom-left corner of the domain.

from dataclasses import dataclass, field

from toporia.framework.params import Param


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
    """Geometric definition of one circular hole in the design domain.

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


@dataclass(frozen=True)
class Scenario:
    """The physical problem: domain, supports, loads, material and material budget.

    Frozen, so a scenario can be shared between runs without one run changing
    another's problem; use dataclasses.replace or Run.updated for variants.

    If no supports or load points are given, the problem builder falls back to
    a clamped left edge and a mid-height load on the right, so Scenario() on
    its own is always solvable.
    """

    # ── Design domain [mm] ────────────────────────────────────────────────────
    Lx: float = 100.0   # domain width
    Ly: float = 50.0    # domain height

    # ── Regions with a prescribed state ───────────────────────────────────────
    # Circular holes: void inside r_void, a solid ring out to r_passive, and
    # optionally a support ("fixed") or a load ("load") on the ring.
    holes: list[HoleConfig] = field(default_factory=list)
    # Polygons forced to stay full or empty.
    enforced_areas: list[EnforcedArea] = field(default_factory=list)

    # ── Supports and load points ──────────────────────────────────────────────
    edge_constraints:  list[EdgeConstraint]  = field(default_factory=list)
    point_constraints: list[PointConstraint] = field(default_factory=list)
    point_loads:       list[PointLoad]       = field(default_factory=list)

    # ── Load cases ────────────────────────────────────────────────────────────
    # Magnitude and direction of the force applied at every load point and load
    # hole.  Several cases are combined as a weighted sum of compliances.
    load_cases: list[LoadCase] = field(
        default_factory=lambda: [LoadCase(Fmag=1.0, Fa=0.0, weight=1.0)]
    )

    # ── Material budget ───────────────────────────────────────────────────────
    # Enforced by every method, and the starting design.
    volfrac: float = 0.5   # fraction of the domain that may be solid

    # ── What is optimised ─────────────────────────────────────────────────────
    # The objective to minimise, and constraints on top of the volume budget,
    # as {"type": <response name>, <param>: <value>} specs.  Response types and
    # their parameters: toporia.plugins.responses.RESPONSES.
    # Example: constraints=[{"type": "stress", "limit": 10.0}]
    objective: dict = field(default_factory=lambda: {"type": "compliance"})
    constraints: list = field(default_factory=list)

    # ── Material (linear elastic, normalised) ─────────────────────────────────
    E0:   float = 1.0     # Young's modulus of solid material
    Emin: float = 1e-9    # stiffness of void; keeps the stiffness matrix non-singular
    nu:   float = 0.3     # Poisson's ratio


# Param declarations for the scenario fields the GUI and sweeps expose.
SCENARIO_PARAMS = (
    Param("volfrac", 0.5, "Vol fraction",
          "Target fraction of solid material allowed in the design.",
          min=0.01, max=1.0, step=0.05, decimals=3),
)
