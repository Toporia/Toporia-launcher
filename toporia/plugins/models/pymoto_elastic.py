# library/models/pymoto_elastic.py — linear elasticity on a pyMOTO module network.
#
# pyMOTO (https://github.com/aatmdelissen/pyMOTO, MIT) builds a topology
# optimisation problem as a network of modules and backpropagates through it,
# so no sensitivity is written by hand here.  This model translates Toporia's
# problem geometry into a pyMOTO network and reads the requested responses and
# their gradients back out:
#
#     x ─DensityFilter─> pin enforced regions ─┬─SIMP─> AssembleStiffness ─> LinSolve ─> u ─> compliance
#                                               ├───────────────────────────────────────────> volume
#                                               └─ ρ^q · von Mises(Stress(u)) ─p-norm────> stress constraint
#
# Objectives: compliance or volume.  Constraints: any number of peak von Mises
# stress limits (library/responses/stress.py), over every load case.
#
# It computes its responses itself, by backpropagation through its own network,
# so it is a whole model rather than a physics engine for library/models/assembled.py:
# its responses are listed by name in its Capabilities, and Toporia's filter
# pipeline does not apply.
#
# It is also the contract's canary: pyMOTO knows nothing about Toporia, so if a
# change to core/ cannot be satisfied here without conversion code, the
# contract has grown a Toporia-specific assumption.
#
# Requires the optional dependency:  pip install "toporia[pymoto]"

import numpy as np

from toporia.framework.parts.method import Capabilities
from toporia.framework.parts.model import ConstraintValue, Evaluation, Model
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE
from toporia.plugins.responses import resolve_response
from toporia.plugins.responses.stress import VON_MISES_2D
from toporia.plugins.shared_params import PENAL, RMIN

IMPORT_HINT = (
    "This requires the optional pyMOTO dependency.\n"
    "Install it with:  pip install pymoto"
)


def import_pymoto():
    """Import pyMOTO, or explain how to install it.

    Always import pyMOTO through this function.  pyMOTO calls
    matplotlib.use("TkAgg") as a side effect of being imported
    (pymoto/modules/io.py).  That backend is only for pyMOTO's own interactive
    plot windows, which Toporia never uses, and the switch does real harm:

      - inside the Qt GUI matplotlib refuses it outright ("Cannot load backend
        'TkAgg' ... as 'qt' is currently running"), so the import fails;
      - elsewhere it would hijack plotting for the whole process, e.g. the CLI
        on a machine without a display.

    So the switch is suppressed for the duration of the import.  The install
    hint is only given when pyMOTO itself is missing; any other import error
    keeps its own message.
    """
    import matplotlib

    use = matplotlib.use
    matplotlib.use = lambda *args, **kwargs: None   # swallow pyMOTO's matplotlib.use("TkAgg")
    try:
        import pymoto
    except ModuleNotFoundError as exc:
        if exc.name != "pymoto":
            raise
        raise ImportError(IMPORT_HINT) from exc
    finally:
        matplotlib.use = use
    return pymoto


_enforce_bounds_class = None


def _enforce_bounds_module(pym):
    """Build (once) a pyMOTO Module that pins enforced elements after filtering.

    Toporia enforces passive and void regions on the *physical* density: a hole
    must actually be a hole in the manufactured part.  Bounding the design
    variables alone is not enough, because the density filter averages across
    the boundary and smears material back into the hole.

    The adjoint drops the sensitivity of every pinned element: those elements
    cannot move, so they must not steer the optimiser.

    Defined lazily because it subclasses pymoto.Module, and pyMOTO is optional.
    """
    global _enforce_bounds_class
    if _enforce_bounds_class is None:

        class _EnforceBounds(pym.Module):
            def __init__(self, lower, upper):
                self.lower = lower
                self.free = (upper - lower) > 0

            def __call__(self, x):
                return np.where(self.free, x, self.lower)

            def _sensitivity(self, dfdy):
                return np.where(self.free, dfdy, 0.0)

        _enforce_bounds_class = _EnforceBounds
    return _enforce_bounds_class


class PymotoElasticModel(Model):
    """Linear elastic SIMP design on a pyMOTO network: compliance or volume, stress limits."""

    name = "pymoto_elastic"
    label = "Linear elasticity, pyMOTO network"
    order = 20
    dependencies = ("pymoto",)
    params = (PENAL, RMIN)
    # pyMOTO applies its own density filter inside the network (radius = rmin),
    # so the Toporia filter pipeline is not used.
    capabilities = Capabilities(
        variable_kind="density", accepts_filters=False,
        objectives=("compliance", "volume"), constraints=("stress",), max_constraints=None,
        needs_constraint=("volume",),
    )

    def initialize(self, problem, solver, settings):
        pym = import_pymoto()
        self.problem = problem
        scenario = problem.scenario
        self.objective_name = resolve_response(scenario.objective, OBJECTIVE_ROLE)[0].name
        stress_settings = [resolve_response(spec, CONSTRAINT_ROLE)[1] for spec in scenario.constraints]

        domain = pym.VoxelDomain(problem.nelx, problem.nely)
        # pyMOTO numbers elements x-fastest, which is a C-order ravel of (nely, nelx).
        self.lb = problem.lower_bound.ravel()
        self.ub = problem.upper_bound.ravel()
        self.volume_limit = domain.nel * scenario.volfrac

        forces, weights = self._load_cases(domain)
        self.s_x = pym.Signal("x", self.initial_design())
        s_f = pym.Signal("f", forces)
        s_w = pym.Signal("w", weights)

        with pym.Network() as self.network:
            self._filter = pym.DensityFilter(domain, radius=settings["rmin"])
            self._pin = _enforce_bounds_module(pym)(self.lb, self.ub)
            s_physical = self._pin(self._filter(self.s_x))
            s_stiffness = pym.MathExpression(
                f"{scenario.Emin} + inp0^{settings['penal']}*({scenario.E0}-{scenario.Emin})"
            )(s_physical)
            s_K = pym.AssembleStiffness(
                domain, bc=self._fixed_dofs(domain), e_modulus=1.0,
                poisson_ratio=scenario.nu, plane="stress",
            )(s_stiffness)
            s_u = pym.LinSolve()(s_K, s_f)
            s_per_case = pym.EinSum("ij,ij->j")(s_u, s_f)   # compliance per load case
            self.s_compliance = pym.EinSum("j,j->")(s_per_case, s_w)
            self.s_volume = pym.EinSum("i->")(s_physical)
            self._stress = [
                self._stress_constraint(pym, domain, s_u, s_physical, forces.shape[1], values)
                for values in stress_settings
            ]
        self._stress_limits = [values["limit"] for values in stress_settings]
        self.s_objective = self.s_volume if self.objective_name == "volume" else self.s_compliance

    def _stress_constraint(self, pym, domain, s_u, s_physical, n_cases, settings):
        """Build g = ‖ρ^q · von Mises‖_p / limit − 1 over every element and load case."""
        scenario = self.problem.scenario
        s_v = pym.Signal("von_mises_matrix", VON_MISES_2D)
        relaxed = []
        for k in range(n_cases):
            s_stress = pym.Stress(domain, e_modulus=scenario.E0, poisson_ratio=scenario.nu,
                                  plane="stress")(s_u[:, k])
            s_squared = pym.EinSum("ij,ik,kj->j")(s_stress, s_v, s_stress)
            s_von_mises = pym.MathExpression("sqrt(inp0 + 1e-12)")(s_squared)
            relaxed.append(pym.MathExpression(f"inp0^{settings['q']}*inp1")(s_physical, s_von_mises))
        s_relaxed = relaxed[0] if n_cases == 1 else pym.Concatenate()(*relaxed)
        scaling = pym.AggScaling("max") if settings["adaptive"] else None
        s_peak = pym.PNorm(p=settings["p"], scaling=scaling)(s_relaxed)
        s_constraint = pym.MathExpression(f"inp0/{settings['limit']} - 1")(s_peak)
        return s_constraint, s_relaxed

    # ── The Model interface ───────────────────────────────────────────────────

    def initial_design(self):
        return np.clip(np.full(self.lb.size, self.problem.scenario.volfrac), self.lb, self.ub)

    def bounds(self):
        return self.lb, self.ub

    def physical(self, x):
        # Called with plain arrays, pyMOTO modules compute without touching the
        # network, so this runs only the filter and the pinning — no FE solve.
        density = self._pin(self._filter(np.asarray(x, dtype=float)))
        return density.reshape(self.problem.nely, self.problem.nelx)

    def evaluate(self, x, gradients=True):
        self.s_x.state = np.asarray(x, dtype=float)
        self.network.response()
        gradient = self._gradient if gradients else (lambda response: None)

        # `exact` is the true peak against the limit, so the result is judged
        # on the real stress rather than on the smooth p-norm.
        constraints = tuple(
            ConstraintValue("stress", float(s_constraint.state), gradient(s_constraint),
                            exact=float(np.max(s_relaxed.state)) / limit - 1.0)
            for (s_constraint, s_relaxed), limit in zip(self._stress, self._stress_limits)
        )
        reported = {}
        if self.objective_name != "compliance":
            reported["compliance"] = float(self.s_compliance.state)
        for i, (_, s_relaxed) in enumerate(self._stress):
            key = "max_stress" if len(self._stress) == 1 else f"max_stress_{i}"
            reported[key] = float(np.max(s_relaxed.state))

        return Evaluation(
            objective=float(self.s_objective.state),
            objective_gradient=gradient(self.s_objective),
            volume=self.s_volume.state,
            volume_gradient=gradient(self.s_volume),
            constraints=constraints,
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
    # Toporia describes boundary conditions as node masks with no DOF numbering,
    # so pyMOTO's numbering (node = j*(nelx+1)+i, dof = 2*node+component) can be
    # applied directly.  Nothing here converts between conventions.

    def _nodes(self, domain, mask):
        """(nely+1, nelx+1) boolean mask -> pyMOTO node numbers."""
        rows, cols = np.nonzero(mask)
        return domain.get_nodenumber(cols, rows)

    def _fixed_dofs(self, domain):
        problem = self.problem
        parts = []
        nodes = self._nodes(domain, problem.fixed_nodes)
        if nodes.size:
            parts.append(domain.get_dofnumber(nodes, np.array([0, 1]), 2).ravel())
        nodes = self._nodes(domain, problem.fixed_x_nodes)
        if nodes.size:
            parts.append(np.atleast_1d(domain.get_dofnumber(nodes, 0, 2)))
        nodes = self._nodes(domain, problem.fixed_y_nodes)
        if nodes.size:
            parts.append(np.atleast_1d(domain.get_dofnumber(nodes, 1, 2)))
        return np.unique(np.concatenate(parts)) if parts else np.array([], dtype=int)

    def _load_cases(self, domain):
        """Build the (ndof, n_load_cases) block right-hand side and its weights."""
        load_cases = self.problem.scenario.load_cases
        forces = np.zeros((domain.nnodes * 2, len(load_cases)))
        for k, case in enumerate(load_cases):
            angle = np.deg2rad(case.Fa)
            vector = case.Fmag * np.array([np.cos(angle), np.sin(angle)])
            for mask in self.problem.load_node_sets:
                nodes = self._nodes(domain, mask)
                per_node = vector / max(nodes.size, 1)
                forces[domain.get_dofnumber(nodes, 0, 2), k] += per_node[0]
                forces[domain.get_dofnumber(nodes, 1, 2), k] += per_node[1]
        return forces, np.array([case.weight for case in load_cases], dtype=float)
