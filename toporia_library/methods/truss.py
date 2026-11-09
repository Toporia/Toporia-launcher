# methods/truss.py — truss topology on a ground structure, then a continuum check (To do item 3).
#
# Stage 1, the truss: bar areas on a ground structure (plugins/physics/truss.py) are sized
# for minimum compliance under the volume budget by the optimality-criteria update
#     a_i ← a_i · (−dC/da_i / (λ L_i))^½,   within move limits and [a_min, a_max],
# with λ found by bisection so that Σ a_i L_i = V.  Thin bars are the ones the structure
# does not need.  The design shown during this stage is the truss drawn as a density.
#
# Stage 2, the continuum (when `stage` asks for it): the truss becomes a density field
# (each bar a capsule as wide as its area) and is handed to the continuum solver of the
# same scenario (2-D Q4 or 3-D H8):
#     check    one solve: the peak von Mises stress and compliance of the converted design
#     stress   a density optimisation of the peak stress (p-norm) starting from it, with
#              MMA, a density filter and the same volume budget
# The run moves from stage 1 to stage 2 when the bar areas settle (the relative change
# falls below `truss_tol`) or after `truss_iterations`.
#
# Reference: W. S. Dorn, R. E. Gomory, H. J. Greenberg, J. Mécanique 3 (1964) 25-52; the
# OC update for trusses: M. P. Bendsøe, O. Sigmund, Topology Optimization (2003), sec. 4.1.

from dataclasses import replace

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod


class TrussMethod(OptimizationMethod):
    """Ground-structure truss optimisation, converted to a density and checked or optimised for stress."""

    name = "truss"
    label = "Truss on a ground structure"
    use_when = (
        "To find the load paths first, as bars: fast, clear, 2-D or 3-D. Then let the continuum stage check the "
        "converted design's peak stress, or round it off for stress."
    )
    reference = (
        'W. S. Dorn, R. E. Gomory, H. J. Greenberg, "Automatic design of optimal structures", J. Mécanique 3'
        ' (1964) 25-52; minimum-compliance truss sizing by optimality criteria as in M. P. Bendsoe, O.'
        ' Sigmund, Topology Optimization (2003), sec. 4.1. Papers: https://doi.org/10.1007/978-3-662-05086-6'
    )
    order = 40
    capabilities = Capabilities(variable_kind="truss", dims=(2, 3), objectives=("compliance",))
    params = (
        Param("spacing", 5.0, "Node spacing", "Distance between ground-structure nodes, in mm (rounded so "
              "nodes fall on mesh nodes at both ends of the domain).", min=0.1, max=1000.0, step=1.0, decimals=2),
        Param("reach", 2, "Reach", "Bars connect nodes up to this many grid steps apart along every axis. 1 "
              "gives a braced grid; 2 or 3 give the angles a Michell structure needs.", min=1, max=4),
        Param("move", 0.5, "Move limit", "Largest relative change of a bar area in one iteration.",
              min=0.01, max=10.0, step=0.1, decimals=2),
        Param("min_area", 1e-4, "Minimum area", "Smallest bar area, relative to the largest; keeps the "
              "stiffness matrix solvable while bars vanish.", min=1e-9, max=0.1, decimals=9),
        Param("truss_iterations", 100, "Truss iterations", "Most iterations of the truss stage.", min=1, max=10000),
        Param("truss_tol", 1e-3, "Truss tolerance", "The truss stage ends when no bar area changes by more "
              "than this, relative to the largest.", min=1e-9, max=1.0, decimals=6),
        Param("stage", "stress", "After the truss", "What the continuum stage does with the converted design.",
              choices=(("none", "Nothing: stop at the truss"), ("check", "Check its peak stress"),
                       ("stress", "Optimise it for peak stress"))),
        Param("stress_p", 8.0, "Stress p-norm", "Aggregation exponent of the peak stress in the continuum stage.",
              min=1.0, max=64.0, step=1.0, decimals=1),
    )

    def initialize(self, problem, solver):
        from toporia_library.physics.truss import TrussSolver, ground_structure
        self.problem, self.solver = problem, solver
        self.settings = self.resolve_params(solver)
        self.structure = ground_structure(problem, self.settings["spacing"], int(self.settings["reach"]))
        if not len(self.structure.bars):
            raise ValueError("The ground structure has no bars: make the node spacing smaller")
        if not self.structure.fixed.size:
            raise ValueError("The truss has no support on any of its nodes")
        self.fe = TrussSolver(self.structure, problem.scenario.E0)
        extent = [problem.Lx, problem.Ly] + ([problem.Lz] if problem.dims == 3 else [])
        self.volume_limit = problem.scenario.volfrac * float(np.prod(extent))
        lengths = self.structure.lengths
        self.areas = np.full(len(lengths), self.volume_limit / float(lengths.sum()))
        self.max_area = float(np.max(self.areas)) * 1e3
        self.phase = "truss"
        self.truss_steps = 0
        self.inner = None
        self.change = np.inf
        self.compliance = np.nan
        self.checked = {}
        self._density = self._truss_density()

    # ── Stage 1 ───────────────────────────────────────────────────────────────

    def _oc_step(self):
        displacements, compliance, gradient = self.fe.solve(self.areas)
        self.displacements, self.compliance = displacements, compliance
        lengths, move = self.structure.lengths, self.settings["move"]
        a = self.areas
        low_bound = max(self.settings["min_area"] * float(np.max(a)), 1e-12)
        lower, upper = np.maximum(low_bound, a * (1 - move)), np.minimum(self.max_area, a * (1 + move))
        ratio = np.maximum(-gradient, 0.0) / lengths
        lo, hi = 1e-30, float(np.max(ratio)) * 1e6 + 1.0
        for _ in range(200):
            lam = np.sqrt(lo * hi)
            new = np.clip(a * np.sqrt(ratio / lam), lower, upper)
            if new @ lengths > self.volume_limit:
                lo = lam
            else:
                hi = lam
            if hi / lo < 1 + 1e-10:
                break
        self.change = float(np.max(np.abs(new - a)) / max(float(np.max(a)), 1e-30))
        self.areas = new

    def _truss_density(self):
        from toporia_library.physics.truss import bars_to_density
        return bars_to_density(self.problem, self.structure, self.areas)

    # ── Stage 2 ───────────────────────────────────────────────────────────────

    def _start_continuum(self):
        from toporia_core.framework.problem.mesh import make_problem
        from toporia_core.framework.problem.solver import Solver
        from toporia_library.methods import make_method
        model = "h8" if self.problem.dims == 3 else "q4"
        scenario = replace(self.problem.scenario, objective={"type": "peak_stress", "p": self.settings["stress_p"]},
                           constraints=[])
        solver = Solver(method=f"{model}+mma", filter_specs=[{"type": "density"}], m=self.solver.m,
                        method_params={"move": 0.05})
        problem = make_problem(scenario, self.solver.m)
        inner = make_method(solver.method)
        inner.initialize(problem, solver)
        start = np.clip(self._density, problem.lower_bound, problem.upper_bound)
        inner.x = start                                   # element densities: the problem's shape
        inner.density = inner._model.physical(inner.x)
        self.inner = inner
        self.checked = self._measure(problem, self._density)

    def _measure(self, problem, density):
        """Peak von Mises stress and compliance of a density on the continuum solver."""
        from toporia_core.framework.parts.assembled import material_law
        from toporia_core.framework.problem.solver import Solver
        from toporia_core.framework.registries import CONSTRAINT_ROLE, OBJECTIVE_ROLE, resolve_response
        from toporia_library.models import MODELS
        model = MODELS.get("h8" if problem.dims == 3 else "q4")
        engine = model.physics()
        material = material_law(Solver())
        material.setup(problem)
        engine.initialize(problem, {p.name: p.default for p in model.params}, material)
        state = engine.solve(density)
        out = {}
        for name, spec in (("compliance", {"type": "compliance"}), ("peak_stress", {"type": "stress", "limit": 1.0})):
            cls, values = resolve_response(spec, OBJECTIVE_ROLE if name == "compliance" else CONSTRAINT_ROLE)
            response = cls()
            response.setup(engine, problem, values)
            result = response.evaluate(state, gradient=False)
            out[name] = float(result.exact + 1.0 if name == "peak_stress" else result.value)
        return out

    # ── The interface ─────────────────────────────────────────────────────────

    def step(self, iteration):
        if self.phase == "truss":
            self._oc_step()
            self.truss_steps += 1
            self._density = self._truss_density()
            settled = self.change < self.settings["truss_tol"] or self.truss_steps >= self.settings["truss_iterations"]
            if settled and self.settings["stage"] != "none":
                self._start_continuum()
                self.phase = "check" if self.settings["stage"] == "check" else "stress"
                self.change = np.inf if self.phase == "stress" else 0.0
            elif settled:
                self.phase = "done"
            return
        if self.phase == "stress":
            self.inner.step(iteration)
            self._density = self.inner.get_density()
            self.change = self.inner.get_change()

    def get_density(self):
        return self._density

    def get_responses(self):
        volume = float(np.mean(self._density))
        out = {OBJECTIVE: float(self.compliance), "volume": volume, "truss_compliance": float(self.compliance),
               "bars": float(np.count_nonzero(self.areas > 1e-2 * np.max(self.areas))),
               "stage": {"truss": 1.0, "done": 1.0, "check": 2.0, "stress": 2.0}[self.phase]}
        if self.checked:
            out.update({f"converted_{key}": value for key, value in self.checked.items()})
        if self.phase == "stress" and np.isfinite(self.inner.objective):
            inner = self.inner.get_responses()
            out[OBJECTIVE] = float(inner[OBJECTIVE])
            out["peak_stress"] = float(inner.get("max_stress", inner[OBJECTIVE]))
        return out

    def get_change(self):
        return self.change

    def continuing(self):
        """The truss stage hands over to the continuum stage: the engine must not stop in between."""
        return self.phase == "truss" and self.settings["stage"] != "none"

    def is_converged(self):
        return self.phase in ("check", "done")

    def convergence_reason(self):
        if self.phase == "check":
            return "the truss settled and its converted design was checked"
        if self.phase == "done":
            return "the truss settled"
        return None

    def network(self):
        """The truss for a view: node coordinates, bars, areas and the first load case's bar forces."""
        forces = None
        if getattr(self, "displacements", None):
            forces = self.fe.axial_forces(self.areas, self.displacements[0])
        return {"nodes": self.structure.nodes, "bars": self.structure.bars, "areas": self.areas, "forces": forces}
