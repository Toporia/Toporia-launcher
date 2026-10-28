# plugins/models/pymoto_heat.py — steady heat conduction on a pyMOTO module network.
#
# The cross-check of q4_heat.py: the same problem, solved by someone else's
# finite element code.  pyMOTO (https://github.com/aatmdelissen/pyMOTO, MIT)
# assembles the Poisson matrix itself and backpropagates the sensitivities, so
# nothing here is derived by hand:
#
#     x ─DensityFilter─> pin enforced regions ─┬─ k = kmin + ρ^p (k0 − kmin) ─> AssemblePoisson ─> LinSolve(K, q) ─> T ─> qᵀT
#                                               └──────────────────────────────────────────────────────────────> volume
#
# Objectives: thermal compliance or volume.  Like pymoto_elastic.py it is a
# whole model rather than a physics engine: pyMOTO's own density filter
# replaces Toporia's filter pipeline.
#
# The scenario means the same as for q4_heat: supports are T = 0, a load case's
# Fmag is heat entering at the load points, and the physics parameter
# `heat_source` is generated uniformly (each element hands a quarter of Q·dx·dy
# to each corner).  With the filter radius at 1 element, which leaves the
# design unchanged, both models give the same thermal compliance
# (tests/plugins/test_heat.py).
#
# Requires the optional dependency:  pip install "toporia[pymoto]"

import numpy as np

from toporia.framework.parts.method import Capabilities
from toporia.framework.parts.model import Evaluation, Model
from toporia.framework.parts.response import OBJECTIVE_ROLE
from toporia.plugins.physics._conduction import HEAT_SOURCE
from toporia.plugins.responses import resolve_response
from toporia.plugins.shared_params import PENAL, RMIN

from .pymoto_elastic import _enforce_bounds_module, import_pymoto


class PymotoHeatModel(Model):
    """Steady heat conduction on a pyMOTO network: thermal compliance or volume."""

    name = "pymoto_heat"
    label = "Heat conduction, pyMOTO network"
    use_when = "To cross-check the heat-conduction results against pyMOTO. Needs pyMOTO installed."
    reference = (
        'pyMOTO by A. Delissen et al. (TU Delft), MIT licence: https://github.com/aatmdelissen/pyMOTO'
        ' - its AssemblePoisson module, as a cross-check of the heat engine after M. P. Bendsoe, O.'
        ' Sigmund, Topology Optimization (Springer 2003), section 1.5; A. Gersborg-Hansen et al.,'
        ' Struct. Multidisc. Optim. 31 (2006) 251-259.'
        ' Papers: https://doi.org/10.1007/s00158-005-0584-3'
    )
    order = 50
    dependencies = ("pymoto",)
    params = (PENAL, RMIN, HEAT_SOURCE)
    # pyMOTO applies its own density filter inside the network (radius = rmin).
    capabilities = Capabilities(
        variable_kind="density", accepts_filters=False,
        objectives=("thermal_compliance", "volume"), constraints=(), max_constraints=0,
        needs_constraint=("volume",),
    )

    def initialize(self, problem, solver, settings):
        pym = import_pymoto()
        self.problem = problem
        scenario = problem.scenario
        self.objective_name = resolve_response(scenario.objective, OBJECTIVE_ROLE)[0].name
        domain = pym.VoxelDomain(problem.nelx, problem.nely, unitx=problem.dx, unity=problem.dy)
        # pyMOTO numbers elements x-fastest, which is a C-order ravel of (nely, nelx).
        self.lb = problem.lower_bound.ravel()
        self.ub = problem.upper_bound.ravel()
        self.volume_limit = domain.nel * scenario.volfrac

        heat, weights = self._heat_cases(domain, settings["heat_source"])
        self.s_x = pym.Signal("x", self.initial_design())
        s_q = pym.Signal("q", heat)
        s_w = pym.Signal("w", weights)

        with pym.Network() as self.network:
            self._filter = pym.DensityFilter(domain, radius=settings["rmin"])
            self._pin = _enforce_bounds_module(pym)(self.lb, self.ub)
            s_physical = self._pin(self._filter(self.s_x))
            s_conductivity = pym.MathExpression(
                f"{scenario.Emin} + inp0^{settings['penal']}*({scenario.E0}-{scenario.Emin})"
            )(s_physical)
            s_K = pym.AssemblePoisson(domain, bc=self._sink_dofs(domain))(s_conductivity)
            # Named, not auto-detected, for the same reason as in pymoto_elastic.py.
            s_T = pym.LinSolve(solver=pym.solvers.SolverSparseLU())(s_K, s_q)
            s_per_case = pym.EinSum("ij,ij->j")(s_T, s_q)       # qᵀT per load case
            self.s_compliance = pym.EinSum("j,j->")(s_per_case, s_w)
            self.s_volume = pym.EinSum("i->")(s_physical)
        self.s_objective = self.s_volume if self.objective_name == "volume" else self.s_compliance

    # ── The Model interface ───────────────────────────────────────────────────

    def initial_design(self):
        return np.clip(np.full(self.lb.size, self.problem.scenario.volfrac), self.lb, self.ub)

    def bounds(self):
        return self.lb, self.ub

    def physical(self, x):
        density = self._pin(self._filter(np.asarray(x, dtype=float)))
        return density.reshape(self.problem.nely, self.problem.nelx)

    def evaluate(self, x, gradients=True):
        self.s_x.state = np.asarray(x, dtype=float)
        self.network.response()
        gradient = self._gradient if gradients else (lambda response: None)
        reported = {}
        if self.objective_name != "thermal_compliance":
            reported["thermal_compliance"] = float(self.s_compliance.state)
        return Evaluation(
            objective=float(self.s_objective.state),
            objective_gradient=gradient(self.s_objective),
            volume=self.s_volume.state,
            volume_gradient=gradient(self.s_volume),
            constraints=(),
            reported=reported,
        )

    def _gradient(self, response):
        """Backpropagate one response to the design variables."""
        self.network.reset()
        response.sensitivity = response.state * 0 + 1.0
        self.network.sensitivity()
        gradient = self.s_x.sensitivity
        result = np.zeros_like(self.s_x.state) if gradient is None else np.array(gradient, dtype=float)
        self.network.reset()
        return result

    # ── Geometry translation ──────────────────────────────────────────────────
    # Node masks have no numbering, so pyMOTO's (node = j*(nelx+1)+i, one DOF per
    # node) is applied directly: the row-major ravel of a (nely+1, nelx+1) mask.

    def _sink_dofs(self, domain):
        """The nodes held at T = 0: every support of the scenario, whichever displacement it fixed."""
        problem = self.problem
        sinks = problem.fixed_nodes | problem.fixed_x_nodes | problem.fixed_y_nodes
        return np.flatnonzero(sinks.ravel())

    def _heat_cases(self, domain, heat_source):
        """The (n_nodes, n_load_cases) heat input and the load case weights."""
        problem = self.problem
        nely, nelx = problem.nely, problem.nelx
        # Each element gives a quarter of Q·dx·dy to each corner, so a node receives
        # that quarter once per element touching it.
        touching = np.zeros((nely + 1, nelx + 1))
        for dj in (0, 1):
            for di in (0, 1):
                touching[dj:dj + nely, di:di + nelx] += 1.0
        generated = (heat_source * problem.dx * problem.dy / 4.0 * touching).ravel()

        load_cases = problem.scenario.load_cases
        heat = np.tile(generated[:, None], (1, len(load_cases)))
        for k, case in enumerate(load_cases):
            for mask in problem.load_node_sets:
                nodes = np.flatnonzero(mask.ravel())
                heat[nodes, k] += case.Fmag / max(nodes.size, 1)
        # Heat entering a sink node leaves at once.  Zeroing it keeps qᵀT honest: pyMOTO solves the
        # constrained rows as T = q / (diagonal value), which would otherwise add a small spurious term.
        heat[self._sink_dofs(domain)] = 0.0
        return heat, np.array([case.weight for case in load_cases], dtype=float)
