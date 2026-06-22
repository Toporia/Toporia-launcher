# problem.py — finite element mesh and boundary conditions
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
#                        TopOptConfig.  This is the entry point for the bundled
#                        benchmark problems and the drone-arm example.
#
# The domain is a rectangle of size Lx × Ly mm divided into nelx × nely
# bilinear quad elements (Q4).  Node numbering follows column-major (Fortran)
# order to match the classic top88 MATLAB convention.

from dataclasses import dataclass

import numpy as np

from .config import TopOptConfig


# ── Public interface ──────────────────────────────────────────────────────────

class BaseProblem:
    """Interface contract every topology-optimization problem must fulfill.

    The FEA solver (morpho.methods.base.solve_fea) and all optimization
    algorithms access exactly these attributes.  A custom problem only needs to
    set them — no specific class hierarchy is required, but subclassing
    BaseProblem and calling validate() is the recommended pattern.

    To implement a custom problem
    -----------------------------
    1. Subclass BaseProblem (or duck-type it if you prefer).
    2. In __post_init__ / __init__, set all required attributes listed below.
    3. Call self.validate() at the end of setup to catch omissions early.
    4. Register the problem in morpho/problems/__init__.py so the GUI sees it.

    Attributes
    ----------
    nelx : int
        Number of finite elements along the x-axis (domain width direction).
    nely : int
        Number of finite elements along the y-axis (domain height direction).
    ndof : int
        Total degrees of freedom.  For a 2-D Q4 mesh:
        ndof = 2 * (nelx + 1) * (nely + 1).
    free_dofs : np.ndarray, shape (n_free,), dtype int
        Sorted indices of unconstrained DOFs — the complement of fixed_dofs
        within arange(ndof).
    forces : list[tuple[float, np.ndarray]]
        One entry per load case: (weight, f) where f is an ndof-length force
        vector and weight is its contribution to the weighted compliance sum.
        Weights should sum to 1 to keep the objective scale consistent.
    void_elements : np.ndarray, shape (nely, nelx), dtype bool
        True for elements forced to density 0 (holes, empty regions).
    passive_elements : np.ndarray, shape (nely, nelx), dtype bool
        True for elements forced to density 1 (material rings, mandatories).

    See Also
    --------
    RectangularProblem : reference 2-D rectangular-mesh implementation.
    """

    # Class-level annotations — concrete subclasses must set these as instance vars.
    nelx:             int
    nely:             int
    ndof:             int
    free_dofs:        np.ndarray
    forces:           list
    void_elements:    np.ndarray
    passive_elements: np.ndarray

    def validate(self):
        """Verify all required attributes have been set.

        Call at the end of __post_init__ / __init__ in concrete subclasses.
        Raises NotImplementedError immediately rather than letting the solver
        encounter a confusing AttributeError mid-run.
        """
        required = ["nelx", "nely", "ndof", "free_dofs", "forces",
                    "void_elements", "passive_elements"]
        missing = [a for a in required if not hasattr(self, a)]
        if missing:
            raise NotImplementedError(
                f"{type(self).__name__} did not set the following required "
                f"BaseProblem attributes: {missing}"
            )


# ── Reference implementation ──────────────────────────────────────────────────

@dataclass
class RectangularProblem(BaseProblem):
    """Mesh and boundary conditions for a 2-D rectangular domain.

    Constructed once per run from a TopOptConfig.  The optimisation algorithm
    reads from it but never writes back to it.

    The domain is nelx × nely bilinear quad elements (Q4) spanning Lx × Ly mm.
    Holes, enforced areas, edge constraints, and point loads are all applied
    during __post_init__ and result in the void/passive element masks and the
    fixed/free DOF arrays that the FEA solver needs.
    """
    config: TopOptConfig

    def __post_init__(self):
        cfg = self.config

        # ── Mesh size ─────────────────────────────────────────────────────────
        self.Lx   = cfg.Lx
        self.Ly   = cfg.Ly
        self.nelx = int(round(cfg.Lx * cfg.m))
        self.nely = max(1, int(round(cfg.Ly * cfg.m)))
        self.nn   = (self.nelx + 1) * (self.nely + 1)
        self.ndof = 2 * self.nn

        self.dx = self.Lx / self.nelx
        self.dy = self.Ly / self.nely

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
        self.void_elements    = np.zeros((self.nely, self.nelx), dtype=bool)
        self.passive_elements = np.zeros((self.nely, self.nelx), dtype=bool)
        self.fixed_nodes      = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
        self.fixed_x_nodes    = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
        self.fixed_y_nodes    = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
        self.load_nodes       = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
        self.load_node_sets   = []

        for hole in cfg.holes:
            ed = np.sqrt((self.elem_x - hole.cx) ** 2 + (self.elem_y - hole.cy) ** 2)
            nd = np.sqrt((self.node_x - hole.cx) ** 2 + (self.node_y - hole.cy) ** 2)

            self.void_elements    |= ed <= hole.r_void
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
                raise ValueError(
                    f"EnforcedArea: unknown kind {area.kind!r}. Use 'full' or 'empty'."
                )

        if np.any(self.passive_elements & self.void_elements):
            raise ValueError(
                "Enforced areas conflict: at least one element is marked both full and empty."
            )

        # ── Edge constraints ──────────────────────────────────────────────────
        for ec in cfg.edge_constraints:
            mask = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
            if   ec.edge == "left":   mask[:, 0]  = True
            elif ec.edge == "right":  mask[:, -1] = True
            elif ec.edge == "top":    mask[-1, :] = True
            elif ec.edge == "bottom": mask[0, :]  = True
            else: raise ValueError(
                f"EdgeConstraint: unknown edge {ec.edge!r}. Use 'left', 'right', 'top', or 'bottom'."
            )
            if   ec.dof == "both": self.fixed_nodes   |= mask
            elif ec.dof == "x":    self.fixed_x_nodes |= mask
            elif ec.dof == "y":    self.fixed_y_nodes |= mask
            else: raise ValueError(
                f"EdgeConstraint: unknown dof {ec.dof!r}. Use 'x', 'y', or 'both'."
            )

        # ── Point constraints ─────────────────────────────────────────────────
        for pc in cfg.point_constraints:
            dist = np.hypot(self.node_x - pc.x, self.node_y - pc.y)
            r, c = np.unravel_index(np.argmin(dist), dist.shape)
            if   pc.dof == "both": self.fixed_nodes[r, c]   = True
            elif pc.dof == "x":    self.fixed_x_nodes[r, c] = True
            elif pc.dof == "y":    self.fixed_y_nodes[r, c] = True
            else: raise ValueError(
                f"PointConstraint: unknown dof {pc.dof!r}. Use 'x', 'y', or 'both'."
            )

        # ── Point loads ───────────────────────────────────────────────────────
        for pl in cfg.point_loads:
            dist = np.hypot(self.node_x - pl.x, self.node_y - pl.y)
            r, c = np.unravel_index(np.argmin(dist), dist.shape)
            load_mask = np.zeros((self.nely + 1, self.nelx + 1), dtype=bool)
            load_mask[r, c] = True
            self.load_nodes     |= load_mask
            self.load_node_sets.append(load_mask)

        # Fallback: if no BCs are defined, use simple defaults so FEA is always solvable.
        has_any_fixed = (np.any(self.fixed_nodes) or
                         np.any(self.fixed_x_nodes) or
                         np.any(self.fixed_y_nodes))
        if not has_any_fixed:
            self.fixed_nodes[:, 0] = True
        if not np.any(self.load_nodes):
            self.load_nodes[self.nely // 2, self.nelx] = True
            self.load_node_sets.append(self.load_nodes.copy())

        # ── Force vectors ─────────────────────────────────────────────────────
        self.forces = [
            (lc.weight, self._make_force_vector(lc.Fmag, lc.Fa))
            for lc in cfg.load_cases
        ]
        self.force = self.forces[0][1]   # backward-compatible alias for single-load code

        # ── DOF index arrays ─────────────────────────────────────────────────
        self.fixed_dofs = self._build_fixed_dofs()
        self.free_dofs  = np.setdiff1d(np.arange(self.ndof), self.fixed_dofs)

        self.validate()

    def _node_ids(self):
        """Return a (nely+1) × (nelx+1) grid of global node indices.
        Column-major (Fortran) order matches the top88 numbering convention."""
        return np.arange(self.nn).reshape((self.nely + 1, self.nelx + 1), order="F")

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

    def _nodes_to_dofs(self, node_mask):
        """Convert a boolean node mask to a sorted array of DOF indices."""
        node_ids = self._node_ids()[node_mask]
        dofs = np.empty(2 * len(node_ids), dtype=int)
        dofs[0::2] = 2 * node_ids
        dofs[1::2] = 2 * node_ids + 1
        return np.unique(dofs)

    def _build_fixed_dofs(self):
        """Assemble the sorted array of constrained DOF indices from all masks."""
        node_ids = self._node_ids()
        parts = []
        ids = node_ids[self.fixed_nodes]
        if ids.size:
            parts.append(np.concatenate([2 * ids, 2 * ids + 1]))
        ids = node_ids[self.fixed_x_nodes]
        if ids.size:
            parts.append(2 * ids)
        ids = node_ids[self.fixed_y_nodes]
        if ids.size:
            parts.append(2 * ids + 1)
        if not parts:
            return np.array([], dtype=int)
        return np.unique(np.concatenate(parts))

    def _make_force_vector(self, magnitude, angle_degrees):
        """Build an ndof-long force vector for a given magnitude and direction."""
        force  = np.zeros(self.ndof)
        angle  = np.deg2rad(angle_degrees)
        vector = magnitude * np.array([np.cos(angle), np.sin(angle)])
        node_ids = self._node_ids()
        for load_mask in self.load_node_sets:
            nodes    = node_ids[load_mask]
            per_node = vector / max(len(nodes), 1)
            for node in nodes:
                force[2 * node: 2 * node + 2] += per_node
        return force


# Backward-compatibility alias — existing user code using BracketProblem still works.
BracketProblem = RectangularProblem
