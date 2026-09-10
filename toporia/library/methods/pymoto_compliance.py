# library/methods/pymoto_compliance.py — compliance minimisation delegated to pyMOTO.
#
# pyMOTO (https://github.com/aatmdelissen/pyMOTO, MIT) builds a topology
# optimisation problem as a network of modules and backpropagates through it, so
# no sensitivity is written by hand here.  This module is a translation layer,
# not an algorithm: it maps Toporia's problem geometry onto a pyMOTO network and
# maps pyMOTO's optimiser back onto core.contract.OptimizationMethod.
#
# It exists for two reasons:
#
#   1. It brings pyMOTO's module library (3-D, thermal, stress constraints,
#      GCMMA, multigrid) within reach without reimplementing any of it.
#   2. It is the contract's canary.  pyMOTO knows nothing about Toporia, so if a
#      change to core/contract.py or core/problem.py cannot be satisfied by this
#      adapter without conversion code, the contract has grown a Toporia-specific
#      assumption and should be reconsidered.
#
# Requires the optional dependency:  pip install "toporia[pymoto]"
#
# Known limitation: pyMOTO's MMA divides by (xmax - xmin), so fully pinned design
# variables (passive or void elements) make it emit divide-by-zero warnings.  The
# results are unaffected — those variables cannot move, and the physical density
# is pinned downstream by _EnforceBounds — but the proper fix is to hand the
# optimiser only the free variables.  That needs a design-vector/element mapping,
# which belongs with the Model/Updater split in Phase 4.

import numpy as np

from toporia.core.contract import OBJECTIVE, Capabilities, OptimizationMethod

from ._shared_params import MOVE, PENAL
from .filters.filter_density import RMIN

_IMPORT_HINT = (
    "The 'pymoto' method requires the optional pyMOTO dependency.\n"
    "Install it with:  pip install pymoto"
)

_enforce_bounds_class = None


def _enforce_bounds_module(pym):
    """Build (once) a pyMOTO Module that pins enforced elements after filtering.

    Toporia enforces passive and void regions on the *physical* density, not on
    the design variables: a hole must actually be a hole in the manufactured
    part.  Bounding the design variables alone is not enough, because the density
    filter averages across the boundary and smears material back into the hole.
    Toporia's own methods clamp after filtering for exactly this reason; this is
    the pyMOTO equivalent.

    The adjoint drops the sensitivity of every pinned element, which is correct:
    those elements cannot move, so they must not steer the optimiser.

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



class PymotoComplianceMethod(OptimizationMethod):
    """SIMP compliance minimisation with a pyMOTO network and MMA."""

    name = "pymoto"
    label = "SIMP density via pyMOTO (MMA)"
    order = 40
    params = (PENAL, MOVE, RMIN)
    # pyMOTO applies its own density filter inside the network (radius = rmin),
    # so the Toporia filter pipeline is not used.
    capabilities = Capabilities(variable_kind="density", accepts_filters=False)

    def initialize(self, problem, solver):
        try:
            import pymoto as pym
        except ImportError as exc:  # pragma: no cover - exercised only without pyMOTO
            raise ImportError(_IMPORT_HINT) from exc

        self.problem, self.solver = problem, solver
        self.settings = self.resolve_params(solver)
        self.objective, self.change = np.inf, np.inf
        domain = self.domain = pym.VoxelDomain(problem.nelx, problem.nely)

        bc = self._fixed_dofs(domain)
        forces, weights = self._load_cases(domain)

        # Passive and void regions become variable bounds.  This is exactly the
        # form problem.lower_bound / upper_bound already provide, which is the
        # point: no translation is needed.
        lb = problem.lower_bound.ravel()
        ub = problem.upper_bound.ravel()
        x0 = np.clip(np.full(domain.nel, problem.scenario.volfrac), lb, ub)

        s_x = pym.Signal("x", x0, min=lb, max=ub)
        s_f = pym.Signal("f", forces)
        s_w = pym.Signal("w", weights)

        with pym.Network() as network:
            s_smeared = pym.DensityFilter(domain, radius=self.settings["rmin"])(s_x)
            s_filtered = _enforce_bounds_module(pym)(lb, ub)(s_smeared)
            s_stiff = pym.MathExpression(
                f"{problem.scenario.Emin} + inp0^{self.settings['penal']}*({problem.scenario.E0}-{problem.scenario.Emin})"
            )(s_filtered)
            s_K = pym.AssembleStiffness(
                domain, bc=bc, e_modulus=1.0, poisson_ratio=problem.scenario.nu, plane="stress"
            )(s_stiff)
            s_u = pym.LinSolve()(s_K, s_f)
            s_per_case = pym.EinSum("ij,ij->j")(s_u, s_f)   # compliance per load case
            s_compliance = pym.EinSum("j,j->")(s_per_case, s_w)
            s_volume = pym.EinSum("i->")(s_filtered)
            s_constraint = pym.MathExpression(
                f"inp0/{domain.nel * problem.scenario.volfrac} - 1"
            )(s_volume)
        s_compliance.tag, s_constraint.tag = "compliance", "volume"

        self.s_filtered, self.s_constraint = s_filtered, s_constraint
        self.optimizer = pym.MMA(
            s_x, [s_compliance, s_constraint], network,
            move=self.settings["move"], xmin=lb, xmax=ub, verbosity=0,
        )
        self.design = self.optimizer.x
        self.density = self.s_filtered.state.reshape(problem.nely, problem.nelx)

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

    # ── The contract ──────────────────────────────────────────────────────────

    def step(self, iteration):
        """One MMA step.

        pyMOTO's Optimizer exposes a public single-iteration `step()` beneath its
        own `optimize()` loop, so Toporia keeps ownership of the loop, the
        stopping rule and the live-update callback.
        """
        design, responses, _ = self.optimizer.step(x=self.design)
        self.objective = float(responses[0])
        self.constraint = float(responses[1])
        self.density = self.s_filtered.state.reshape(self.problem.nely, self.problem.nelx)
        self.change = float(np.max(np.abs(design - self.design)))
        self.design = design

    def get_density(self):   return self.density
    def get_change(self):    return self.change

    def get_responses(self):
        return {
            OBJECTIVE: self.objective,
            "volume": float(self.density.mean()),
            "volume_constraint": self.constraint,
        }
