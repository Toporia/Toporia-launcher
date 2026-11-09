# methods/truss.py — truss topology on a ground structure, kept as bars (To do item 3).
#
# The design variables are the bar areas a of a ground structure (toporia_library/physics/truss.py):
# a grid of nodes with a bar to every neighbour within reach.  Each iteration solves the
# truss and updates the areas by optimality criteria,
#
#     a_i ← a_i · (s_i / (λ V_i))^½,   within move limits and [a_min, a_max],
#
# where V_i = L_i + 2ℓ is the material length of bar i (ℓ the joint length, 0 for pins) and
# λ meets the volume budget Σ a_i V_i = V by bisection.  The sensitivity s_i is
#
#     compliance          s_i = −∂C/∂a_i = Σ_k w_k (E/L_i)(c·Δu_ik)²              (minimise C)
#     eigenfrequency      s_i =  ∂λ₁/∂a_i                                          (maximise λ₁ = ω₁²)
#
# Thin bars are the ones the structure does not need.  The design stays bars: the method
# never maps it onto the finite-element mesh.  The density the engine records each iteration
# (the one field every method must hand over) is only a drawing of the bars for the run's
# record and images; the app shows the bars themselves.  A clean solid to make is the
# post-processor truss_solid, run only when it is in the post-processing list.
#
# The nodes (toporia_library/physics/truss_nodes.py): pins by default, as in the literature; joints
# with material (`joint_length` ℓ > 0) and anchored nodes (spring objects of the Problem page,
# or `anchor_stiffness` on every free node) are Toporia's own additions.
#
# Reference: W. S. Dorn, R. E. Gomory, H. J. Greenberg, J. Mécanique 3 (1964) 25-52; the OC
# update for trusses as in M. P. Bendsøe, O. Sigmund, Topology Optimization (2003), sec. 4.1.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod


class TrussMethod(OptimizationMethod):
    """Ground-structure truss optimisation: bar areas for stiffness or frequency, kept as bars."""

    name = "truss"
    label = "Truss on a ground structure"
    use_when = (
        "To find the load paths as bars: fast and clear, 2-D or 3-D. Add the post-processor 'Truss to a clean "
        "solid' to get a shape to make."
    )
    reference = (
        'W. S. Dorn, R. E. Gomory, H. J. Greenberg, "Automatic design of optimal structures", J. Mécanique 3'
        ' (1964) 25-52; minimum-compliance truss sizing by optimality criteria as in M. P. Bendsoe, O.'
        ' Sigmund, Topology Optimization (2003), sec. 4.1. Joint and anchored nodes are Toporia\'s own.'
        ' Papers: https://doi.org/10.1007/978-3-662-05086-6'
    )
    order = 40
    capabilities = Capabilities(variable_kind="truss", dims=(2, 3), objectives=("compliance", "eigenfrequency"),
                                supports_springs=True)        # spring objects anchor nodes
    params = (
        Param("spacing", 5.0, "Node spacing", "Distance between ground-structure nodes, in mm (rounded so "
              "nodes fall on mesh nodes at both ends of the domain).", min=0.1, max=1000.0, step=1.0, decimals=2),
        Param("reach", 2, "Reach", "Bars connect nodes up to this many grid steps apart along every axis. 1 "
              "gives a braced grid; 2 or 3 give the angles a Michell structure needs.", min=1, max=4),
        Param("move", 0.5, "Move limit", "Largest relative change of a bar area in one iteration.",
              min=0.01, max=10.0, step=0.1, decimals=2),
        Param("min_area", 1e-4, "Minimum area", "Smallest bar area, relative to the largest; keeps the "
              "stiffness matrix solvable while bars vanish.", min=1e-9, max=0.1, decimals=9),
        Param("joint_length", 0.0, "Joint length", "Toporia's own joint model: every bar end brings this length "
              "of its cross-section into the node, so joints have volume and mass. 0 is an ideal pin.",
              min=0.0, max=1000.0, step=0.5, decimals=3, units="mm"),
        Param("anchor_stiffness", 0.0, "Anchor every node", "Toporia's own anchored nodes: a spring of this "
              "stiffness ties every free node to where it started. Spring objects on the Problem page anchor "
              "only their nodes.", min=0.0, max=1e9, step=0.1, decimals=6, units="N/mm"),
        Param("mass_density", 1.0, "Mass density", "Mass per unit volume of the bars and joints, for the "
              "frequency objective.", min=1e-12, max=1e12, decimals=6),
        Param("node_value", "joint_area", "Node value", "What a node shows: a formula of displacement, "
              "joint_area, force, x, y and z, e.g. 'force / joint_area'. Empty shows plain dots."),
    )

    def initialize(self, problem, solver):
        from toporia_library.physics.truss import TrussSolver, ground_structure
        from toporia_library.physics.truss_nodes import anchors, effective_lengths, mass_slope
        self.problem, self.solver = problem, solver
        self.settings = s = self.resolve_params(solver)
        self.structure = ground_structure(problem, s["spacing"], int(s["reach"]))
        if not len(self.structure.bars):
            raise ValueError("The ground structure has no bars: make the node spacing smaller")
        springs = anchors(problem, self.structure, s["anchor_stiffness"])
        if not self.structure.fixed.size and not springs.any():
            raise ValueError("The truss has no support or anchor on any of its nodes")
        self.fe = TrussSolver(self.structure, problem.scenario.E0, springs)
        self.frequency = problem.scenario.objective.get("type") == "eigenfrequency"
        if not self.frequency:
            from toporia_core.framework.variables import compile_expression
            from toporia_library.physics.truss_nodes import NODE_NAMES
            if s["node_value"].strip():
                compile_expression(s["node_value"], set(NODE_NAMES), what="The node value")
        self.material_lengths = effective_lengths(self.structure.lengths, s["joint_length"])
        self.mass_slope = mass_slope(self.structure, s["mass_density"], s["joint_length"])
        extent = [problem.Lx, problem.Ly] + ([problem.Lz] if problem.dims == 3 else [])
        self.domain_volume = float(np.prod(extent))
        self.volume_limit = problem.scenario.volfrac * self.domain_volume
        self.areas = np.full(len(lengths := self.material_lengths), self.volume_limit / float(lengths.sum()))
        self.max_area = float(np.max(self.areas)) * 1e3
        self.change = np.inf
        self.value, self.mode, self.displacements = np.nan, None, None
        self._density = self._drawing()

    def _sensitivity(self):
        """Evaluate the design: the objective value and s_i (positive where more area helps)."""
        if self.frequency:
            from toporia_library.physics.truss_nodes import lumped_mass
            mass = lumped_mass(self.structure, self.areas, self.settings["mass_density"],
                               self.settings["joint_length"])
            lam, self.mode, slope = self.fe.lowest_mode(self.areas, mass, self.mass_slope)
            self.value = lam
            return slope
        self.displacements, self.value, gradient = self.fe.solve(self.areas)
        return -gradient

    def step(self, iteration):
        sensitivity = self._sensitivity()
        a, move, lengths = self.areas, self.settings["move"], self.material_lengths
        low_bound = max(self.settings["min_area"] * float(np.max(a)), 1e-12)
        lower, upper = np.maximum(low_bound, a * (1 - move)), np.minimum(self.max_area, a * (1 + move))
        ratio = np.maximum(sensitivity, 1e-30 * max(float(np.max(np.abs(sensitivity))), 1e-300)) / lengths
        lo, hi = 1e-300, float(np.max(ratio)) * 1e12 + 1.0
        for _ in range(400):
            lam = np.sqrt(lo * hi)
            new = np.clip(a * np.sqrt(ratio / lam), lower, upper)
            if new @ lengths > self.volume_limit:
                lo = lam
            else:
                hi = lam
            if hi / lo < 1 + 1e-12:
                break
        self.change = float(np.max(np.abs(new - a)) / max(float(np.max(a)), 1e-30))
        self.areas = new
        self._density = self._drawing()

    def _drawing(self):
        """The bars drawn on the element grid: only for the engine's record and images."""
        from toporia_library.physics.truss import bars_to_density
        return bars_to_density(self.problem, self.structure, self.areas)

    def get_density(self):
        return self._density

    def get_responses(self):
        objective = -self.value if self.frequency else self.value
        volume = float(self.areas @ self.material_lengths) / self.domain_volume
        out = {OBJECTIVE: float(objective), "truss_volume": volume,
               "bars": float(np.count_nonzero(self.areas > 1e-2 * np.max(self.areas)))}
        if self.frequency and np.isfinite(self.value):
            out["frequency"] = float(np.sqrt(max(self.value, 0.0)) / (2 * np.pi))
        return out

    def get_change(self):
        return self.change

    def network(self):
        """The truss for its view: nodes, bars, areas, bar forces and node values."""
        from toporia_library.physics.truss_nodes import joint_radius, node_values
        forces, displacement = None, None
        if self.displacements:
            displacement = self.displacements[0]
            forces = self.fe.axial_forces(self.areas, displacement)
        elif self.mode is not None:
            displacement = self.mode
        values = node_values(self.settings["node_value"], self.structure, self.areas, displacement, forces)
        document = {"nodes": self.structure.nodes, "bars": self.structure.bars, "areas": self.areas,
                    "forces": forces, "node_values": values, "node_label": self.settings["node_value"].strip() or None}
        if self.settings["joint_length"] > 0:
            document["joint_radius"] = joint_radius(self.structure, self.areas, self.settings["joint_length"])
        return document
