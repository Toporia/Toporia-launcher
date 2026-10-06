# framework/problem/mesh.py — finite element mesh and boundary conditions
#
# Defines two things:
#
#   BaseProblem — the interface contract that every topology-optimisation problem
#                 must fulfill.  The FEA solver and all optimizers read the
#                 attributes listed on this class.  To define a new problem,
#                 subclass BaseProblem and set every listed attribute in __post_init__
#                 (dataclasses) or __init__.  Call validate() at the end of setup
#                 to catch incomplete implementations at construction time.
#
#   RectangularProblem — the reference implementation: a 2-D rectangle of Q4
#                        bilinear elements with holes, edge constraints, point
#                        loads, and enforced passive/void regions, all driven by
#                        a Scenario.  This is the entry point for the bundled
#                        benchmark problems and the drone-arm example.
#
#   BoxProblem         — the same scenario in 3-D: the rectangle extruded to a
#                        depth Lz (Scenario.Lz > 0) and divided into
#                        nelx × nely × nelz brick elements.  Holes become
#                        through-holes, edges become faces, and point supports
#                        and loads become lines through the thickness.
#
#   make_problem(scenario, m) builds whichever of the two the scenario asks for.
#
# The domain is a rectangle of size Lx × Ly mm divided into nelx × nely
# bilinear quad elements (Q4).  Node numbering follows column-major (Fortran)
# order to match the classic top88 MATLAB convention.
#
# Every element field has the problem's `shape`: (nely, nelx) in 2-D and
# (nelz, nely, nelx) in 3-D, so a 2-D field is the 3-D one without its first
# axis and code written for `shape` works in both.  `dims` is 2 or 3.

from dataclasses import dataclass

import numpy as np

from toporia.framework.problem.scenario import Scenario

# ── Public interface ──────────────────────────────────────────────────────────


class BaseProblem:
    """Interface contract every topology-optimization problem must fulfill.

    A problem describes GEOMETRY only: where material may go, where the
    structure is held, and where loads are applied.  It deliberately carries no
    degree-of-freedom numbering and no force vectors — those are conventions of
    a particular finite element solver, and live in toporia.plugins.physics.

    That separation is what lets a foreign solver (a 3-D mesh, a pyMOTO
    network) consume the same problem without any translation layer.

    To implement a custom problem
    -----------------------------
    1. Subclass BaseProblem (or duck-type it if you prefer).
    2. In __post_init__ / __init__, set all required attributes listed below.
    3. Call self.validate() at the end of setup to catch omissions early.
    4. Register the problem in toporia/plugins/problems/__init__.py so the GUI sees it.

    Attributes
    ----------
    scenario : framework.problem.scenario.Scenario
        The scenario the problem was built from.  Methods read the material,
        the volume target and the load cases from it.
    dims : int
        2 or 3.
    shape : tuple
        The shape of every element field: (nely, nelx), or (nelz, nely, nelx) in 3-D.
        Node masks have one more node than elements along every axis.
    nelx : int
        Number of finite elements along the x-axis (domain width direction).
    nely : int
        Number of finite elements along the y-axis (domain height direction).
    nn : int
        Total number of mesh nodes: (nelx + 1) * (nely + 1).
    fixed_nodes, fixed_x_nodes, fixed_y_nodes : np.ndarray, shape (nely+1, nelx+1), dtype bool
        Nodes constrained in both / only x / only y.  These are *geometric*
        masks: they carry no degree-of-freedom numbering, so any solver can
        map them onto its own convention.
    load_node_sets : list[np.ndarray], each shape (nely+1, nelx+1), dtype bool
        One node mask per load application region.  The magnitude, direction
        and weight of each load case live in Scenario.load_cases; this
        records only *where* the load acts.
    void_elements : np.ndarray, shape (nely, nelx), dtype bool
        True for elements forced to density 0 (holes, empty regions).
    passive_elements : np.ndarray, shape (nely, nelx), dtype bool
        True for elements forced to density 1 (material rings, mandatories).
    lower_bound, upper_bound : np.ndarray, shape (nely, nelx), dtype float
        Derived from the two masks above; this is the form methods consume.

    See Also
    --------
    RectangularProblem : reference 2-D rectangular-mesh implementation.
    """

    # Class-level annotations — concrete subclasses must set these as instance vars.
    scenario: Scenario
    nelx: int
    nely: int
    nn: int
    fixed_nodes: np.ndarray
    fixed_x_nodes: np.ndarray
    fixed_y_nodes: np.ndarray
    load_node_sets: list
    void_elements: np.ndarray
    passive_elements: np.ndarray

    # ── Derived views ─────────────────────────────────────────────────────────
    # Methods consume per-element bounds, not masks.  Both MMA implementations,
    # the OC bisection and pyMOTO all want the same thing: "how low and how high
    # may this element go".  Deriving them here means there is exactly one source
    # of truth and no method can forget to clamp after an update.

    @property
    def lower_bound(self):
        """Per-element minimum density: 1.0 where solid is enforced, else 0.0."""
        return self.passive_elements.astype(float)

    @property
    def upper_bound(self):
        """Per-element maximum density: 0.0 where void is enforced, else 1.0."""
        return (~self.void_elements).astype(float)

    def validate(self):
        """Verify all required attributes have been set.

        Call at the end of __post_init__ / __init__ in concrete subclasses.
        Raises NotImplementedError immediately rather than letting the solver
        encounter a confusing AttributeError mid-run.
        """
        required = [
            "scenario",
            "nelx",
            "nely",
            "nn",
            "load_node_sets",
            "fixed_nodes",
            "fixed_x_nodes",
            "fixed_y_nodes",
            "void_elements",
            "passive_elements",
        ]
        missing = [a for a in required if not hasattr(self, a)]
        if missing:
            raise NotImplementedError(
                f"{type(self).__name__} did not set the following required BaseProblem attributes: {missing}"
            )


# ── Reference implementation ──────────────────────────────────────────────────


@dataclass
class RectangularProblem(BaseProblem):
    """Mesh and boundary conditions for a 2-D rectangular domain.

    Constructed once per run from a Scenario and a mesh resolution m (Solver.m).  The optimisation algorithm
    reads from it but never writes back to it.

    The domain is nelx × nely bilinear quad elements (Q4) spanning Lx × Ly mm.
    Holes, enforced areas, edge constraints, and point loads are all applied
    during __post_init__ and result in the void/passive element masks and the
    node masks that a finite element solver turns into its own DOF arrays.
    """

    scenario: Scenario
    m: float = 1.0  # mesh resolution in elements per mm (Solver.m)

    def __post_init__(self):
        cfg = self.scenario

        # ── Mesh size ─────────────────────────────────────────────────────────
        self.Lx = cfg.Lx
        self.Ly = cfg.Ly
        self.nelx = int(round(cfg.Lx * self.m))
        self.nely = max(1, int(round(cfg.Ly * self.m)))
        self.nn = (self.nelx + 1) * (self.nely + 1)

        self.dx = self.Lx / self.nelx
        self.dy = self.Ly / self.nely
        self.dims = 2
        self.shape = (self.nely, self.nelx)

        # ── Coordinate grids ─────────────────────────────────────────────────
        self.node_x, self.node_y = np.meshgrid(
            np.linspace(0.0, self.Lx, self.nelx + 1),
            np.linspace(0.0, self.Ly, self.nely + 1),
        )
        self.elem_x, self.elem_y = np.meshgrid(
            (np.arange(self.nelx) + 0.5) * self.dx,
            (np.arange(self.nely) + 0.5) * self.dy,
        )

        # ── Region masks ─────────────────────────────────────────────────────
        self.void_elements = np.zeros((self.nely, self.nelx), dtype=bool)
        self.passive_elements = np.zeros((self.nely, self.nelx), dtype=bool)
        self.fixed_nodes = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
        self.fixed_x_nodes = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
        self.fixed_y_nodes = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
        self.load_nodes = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
        self.load_node_sets = []

        for hole in cfg.holes:
            ed = np.sqrt((self.elem_x - hole.cx) ** 2 + (self.elem_y - hole.cy) ** 2)
            nd = np.sqrt((self.node_x - hole.cx) ** 2 + (self.node_y - hole.cy) ** 2)

            self.void_elements |= ed <= hole.r_void
            self.passive_elements |= (ed > hole.r_void) & (ed <= hole.r_passive)

            if hole.kind == "fixed":
                self.fixed_nodes |= nd <= hole.r_passive
            elif hole.kind == "load":
                load_mask = nd <= hole.r_passive
                self.load_nodes |= load_mask
                self.load_node_sets.append(load_mask)

        for area in cfg.enforced_areas:
            mask = self._polygon_element_mask(area.points)
            if area.kind == "full":
                self.passive_elements |= mask
            elif area.kind == "empty":
                self.void_elements |= mask
            else:
                raise ValueError(f"EnforcedArea: unknown kind {area.kind!r}. Use 'full' or 'empty'.")

        if np.any(self.passive_elements & self.void_elements):
            raise ValueError("Enforced areas conflict: at least one element is marked both full and empty.")

        # ── Edge constraints ──────────────────────────────────────────────────
        for ec in cfg.edge_constraints:
            mask = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
            if ec.edge == "left":
                mask[:, 0] = True
            elif ec.edge == "right":
                mask[:, -1] = True
            elif ec.edge == "top":
                mask[-1, :] = True
            elif ec.edge == "bottom":
                mask[0, :] = True
            else:
                raise ValueError(
                    f"EdgeConstraint: unknown edge {ec.edge!r}. Use 'left', 'right', 'top', or 'bottom'."
                )
            if ec.dof == "both":
                self.fixed_nodes |= mask
            elif ec.dof == "x":
                self.fixed_x_nodes |= mask
            elif ec.dof == "y":
                self.fixed_y_nodes |= mask
            else:
                raise ValueError(f"EdgeConstraint: unknown dof {ec.dof!r}. Use 'x', 'y', or 'both'.")

        # ── Point constraints ─────────────────────────────────────────────────
        for pc in cfg.point_constraints:
            dist = np.hypot(self.node_x - pc.x, self.node_y - pc.y)
            r, c = np.unravel_index(np.argmin(dist), dist.shape)
            if pc.dof == "both":
                self.fixed_nodes[r, c] = True
            elif pc.dof == "x":
                self.fixed_x_nodes[r, c] = True
            elif pc.dof == "y":
                self.fixed_y_nodes[r, c] = True
            else:
                raise ValueError(f"PointConstraint: unknown dof {pc.dof!r}. Use 'x', 'y', or 'both'.")

        # ── Point loads ───────────────────────────────────────────────────────
        for pl in cfg.point_loads:
            dist = np.hypot(self.node_x - pl.x, self.node_y - pl.y)
            r, c = np.unravel_index(np.argmin(dist), dist.shape)
            load_mask = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
            load_mask[r, c] = True
            self.load_nodes |= load_mask
            self.load_node_sets.append(load_mask)

        # Fallback: if no BCs are defined, use simple defaults so FEA is always solvable.
        has_any_fixed = np.any(self.fixed_nodes) or np.any(self.fixed_x_nodes) or np.any(self.fixed_y_nodes)
        if not has_any_fixed:
            self.fixed_nodes[:, 0] = True
        if not np.any(self.load_nodes):
            self.load_nodes[self.nely // 2, self.nelx] = True
            self.load_node_sets.append(self.load_nodes.copy())

        self.validate()

    def _polygon_element_mask(self, points):
        """Return an element-centre mask for a polygon in physical xy coordinates."""
        pts = np.asarray(points, dtype=float)
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError("EnforcedArea points must be a list of (x, y) pairs.")
        if len(pts) < 3:
            raise ValueError("EnforcedArea requires at least three polygon points.")

        x = self.elem_x
        y = self.elem_y
        inside = np.zeros(x.shape, dtype=bool)
        xj, yj = pts[-1]
        for xi, yi in pts:
            crosses = (yi > y) != (yj > y)
            x_intersect = (xj - xi) * (y - yi) / (yj - yi + 1e-300) + xi
            inside ^= crosses & (x < x_intersect)
            xj, yj = xi, yi
        return inside



class BoxProblem(BaseProblem):
    """A scenario in 3-D: its rectangle extruded to the depth Lz, in nelx × nely × nelz bricks.

    The cross-section is the 2-D problem at the same resolution, so everything
    a scenario can say in 2-D carries over: every element and node mask is the
    2-D one repeated through the depth.  Element fields have the shape
    (nelz, nely, nelx), node masks (nelz+1, nely+1, nelx+1).

    Supports clamp the out-of-plane direction as well: a 2-D support is a wall
    through the thickness.  Without that, a scenario held only by rollers (the
    MBB beam) could slide and turn out of its plane.  fixed_z_nodes marks the
    nodes held in z only (none, for an extruded scenario; the attribute is
    there for problems that need it).

    A load spread over a line or surface through the depth is shared between
    the layers of nodes in proportion to the length each one carries: half at
    the two outer layers.  A design that does not vary through the depth then
    behaves exactly as the 2-D design in plane stress with Poisson's ratio 0,
    which is how the 3-D engine is checked against the 2-D one.
    """

    def __init__(self, scenario, m=1.0):
        if scenario.Lz <= 0:
            raise ValueError("BoxProblem needs a scenario with a depth Lz > 0; use RectangularProblem in 2-D")
        self.scenario, self.m = scenario, m
        section = RectangularProblem(scenario, m)
        self.section = section
        self.Lx, self.Ly, self.Lz = section.Lx, section.Ly, scenario.Lz
        self.nelx, self.nely = section.nelx, section.nely
        self.nelz = max(1, int(round(scenario.Lz * m)))
        self.dx, self.dy, self.dz = section.dx, section.dy, self.Lz / self.nelz
        self.dims = 3
        self.shape = (self.nelz, self.nely, self.nelx)
        self.nn = (self.nelx + 1) * (self.nely + 1) * (self.nelz + 1)

        def elements(mask):
            return np.broadcast_to(mask, (self.nelz,) + mask.shape).copy()

        def nodes(mask):
            return np.broadcast_to(mask, (self.nelz + 1,) + mask.shape).copy()

        z_nodes = np.linspace(0.0, self.Lz, self.nelz + 1)
        z_elems = (np.arange(self.nelz) + 0.5) * self.dz
        self.node_z = np.broadcast_to(z_nodes[:, None, None], (self.nelz + 1,) + section.node_x.shape).copy()
        self.node_x, self.node_y = nodes(section.node_x), nodes(section.node_y)
        self.elem_z = np.broadcast_to(z_elems[:, None, None], self.shape).copy()
        self.elem_x, self.elem_y = elements(section.elem_x), elements(section.elem_y)

        self.void_elements = elements(section.void_elements)
        self.passive_elements = elements(section.passive_elements)
        self.fixed_nodes = nodes(section.fixed_nodes)
        # A 2-D roller is a wall through the thickness: it holds z as well.
        self.fixed_x_nodes = nodes(section.fixed_x_nodes)
        self.fixed_y_nodes = nodes(section.fixed_y_nodes)
        self.fixed_z_nodes = self.fixed_x_nodes | self.fixed_y_nodes
        self.load_nodes = nodes(section.load_nodes)
        self.load_node_sets = [nodes(mask) for mask in section.load_node_sets]
        # Share of a through-depth load carried by each layer of nodes.
        layers = np.ones(self.nelz + 1)
        layers[[0, -1]] = 0.5
        self.layer_weights = layers / layers.sum()
        self.validate()


def projection(field):
    """A 2-D picture of an element field: the field itself in 2-D, its average through the depth in 3-D.

    The average is what an X-ray along z would show: 1 where the design is
    solid all the way through, grey where only part of the depth is.  Images,
    comparisons and the GUI's live view draw this; the full 3-D field is kept
    as well (final_density.npy).
    """
    field = np.asarray(field)
    return field.mean(axis=0) if field.ndim == 3 else field


def make_problem(scenario, m=1.0):
    """The meshed problem for a scenario: 2-D unless it has a depth (Scenario.Lz > 0)."""
    return BoxProblem(scenario, m) if getattr(scenario, "Lz", 0.0) > 0 else RectangularProblem(scenario, m)
