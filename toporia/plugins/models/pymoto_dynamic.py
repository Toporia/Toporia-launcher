# plugins/models/pymoto_dynamic.py — natural frequencies on a pyMOTO module network.
#
# The vibration counterpart of pymoto_elastic.py, and the independent check of
# plugins/physics/q4_dynamic.py: pyMOTO assembles the stiffness and the consistent
# mass and solves the eigenproblem itself, so none of Toporia's mass or eigenvalue
# sensitivities are used here.
#
#     x ─DensityFilter─> pin ─┬─SIMP─> AssembleStiffness ─────────┐
#                             └─mass interpolation─> AssembleMass ─┴─> EigenSolve ─> λ ─> smooth minimum
#
# Objective: eigenfrequency (the same smooth minimum of the lowest `modes`
# eigenvalues as plugins/responses/eigenfrequency.py, scaled the same way).  The
# mass is the consistent one, with the same Pedersen-type low-density fix and
# attached mass as the Q4 engine, so on the same density both give the same
# eigenvalues (tests/plugins/test_dynamics.py).
#
# Requires the optional dependency:  pip install "toporia[pymoto]"

import numpy as np
from scipy.sparse import diags

from toporia.framework.parts.method import Capabilities
from toporia.framework.parts.model import Evaluation
from toporia.framework.parts.response import OBJECTIVE_ROLE
from toporia.plugins.physics.q4_dynamic import (
    ATTACHED_MASS,
    LOW_DENSITY_BELOW,
    LOW_DENSITY_EXPONENT,
    MASS_DENSITY,
    mass_interpolation,
)
from toporia.plugins.responses import resolve_response
from toporia.plugins.responses.eigenfrequency import soft_minimum
from toporia.plugins.shared_params import PENAL, RMIN

from .pymoto_elastic import PymotoElasticModel, _enforce_bounds_module, import_pymoto

_modules = {}


def _network_modules(pym):
    """Build (once) the two pyMOTO modules this model adds; lazy because pyMOTO is optional."""
    if not _modules:

        class MassInterpolation(pym.Module):
            """m(ρ) per element: the density itself, with Pedersen's faster fall below the threshold."""

            def __init__(self, threshold, exponent):
                self.threshold, self.exponent = threshold, exponent

            def __call__(self, rho):
                mass, self.slope = mass_interpolation(rho, self.threshold, self.exponent)
                return mass

            def _sensitivity(self, dmass):
                return dmass * self.slope

        class SmoothMinimum(pym.Module):
            """−λ_agg / λ_ref of the eigenvalues: the aggregate of response eigenfrequency, scaled by the first design's."""

            def __init__(self, p):
                self.p, self.reference = p, None

            def __call__(self, eigenvalues):
                aggregate, self.weights = soft_minimum(np.asarray(eigenvalues, dtype=float), self.p)
                if self.reference is None:
                    self.reference = aggregate
                return -aggregate / self.reference

            def _sensitivity(self, dobjective):
                return -dobjective * self.weights / self.reference

        class EigenSolve(pym.EigenSolve):
            """pyMOTO's EigenSolve, made deterministic: a fixed start vector and a fixed linear solver.

            ARPACK's own start vector is random, which changes the last digits from call to call; the
            conformance check (and a reproducible run) needs equal values for equal designs.
            """

            def _sparse_eigs(self, A, B=None):
                import scipy.sparse.linalg as spla
                if self.sigma is None:
                    self.sigma = 0.0
                if self.Ainv is None:
                    # Named, as in pymoto_elastic.py: the auto-detected PARDISO is multithreaded and
                    # differs in the last digits from call to call; SciPy's sparse LU does not.
                    self.Ainv = pym.solvers.SolverSparseLU()
                self.Ainv.update(A)
                operator = spla.LinearOperator(A.shape, matvec=self.Ainv.solve)
                start = np.random.default_rng(0).standard_normal(A.shape[0])
                return spla.eigsh(A, M=B, k=self.nmodes, OPinv=operator, sigma=self.sigma, mode=self.mode, v0=start)

        _modules.update(mass=MassInterpolation, minimum=SmoothMinimum, eigen=EigenSolve)
    return _modules


class PymotoDynamicModel(PymotoElasticModel):
    """Maximise a natural frequency on a pyMOTO network of stiffness, consistent mass and eigensolver."""

    name = "pymoto_dynamic"
    label = "Vibration, pyMOTO network"
    reference = (
        'pyMOTO by A. Delissen et al. (TU Delft), MIT licence: https://github.com/aatmdelissen/pyMOTO -'
        ' its AssembleMass and EigenSolve modules; the mass fix is that of N. L. Pedersen, Struct. Multidisc.'
        ' Optim. 20 (2000) 2-11.'
        ' Papers: https://doi.org/10.1007/s001580050130'
    )
    order = 21
    dependencies = ("pymoto",)
    params = (PENAL, RMIN, MASS_DENSITY, LOW_DENSITY_BELOW, LOW_DENSITY_EXPONENT, ATTACHED_MASS)
    capabilities = Capabilities(
        variable_kind="density", accepts_filters=False,
        objectives=("eigenfrequency",), constraints=(), max_constraints=0,
    )

    def initialize(self, problem, solver, settings):
        pym = import_pymoto()
        modules = _network_modules(pym)
        self.problem = problem
        scenario = problem.scenario
        values = resolve_response(scenario.objective, OBJECTIVE_ROLE)[1]

        # Unit-thickness elements of their true size: the stiffness does not depend on it in 2-D, the mass does.
        domain = pym.VoxelDomain(problem.nelx, problem.nely, unitx=problem.dx, unity=problem.dy)
        self.lb = problem.lower_bound.ravel()
        self.ub = problem.upper_bound.ravel()
        self.volume_limit = domain.nel * scenario.volfrac
        fixed = self._fixed_dofs(domain)

        attached = np.zeros(domain.nnodes * 2)
        nodes = np.unique(np.concatenate([self._nodes(domain, mask) for mask in problem.load_node_sets]
                                         or [np.array([], dtype=int)]))
        if settings["attached_mass"] > 0 and nodes.size:
            attached[2 * nodes] = attached[2 * nodes + 1] = settings["attached_mass"] / nodes.size
        attached[fixed] = 0.0

        self.s_x = pym.Signal("x", self.initial_design())
        with pym.Network() as self.network:
            self._filter = pym.DensityFilter(domain, radius=settings["rmin"])
            self._pin = _enforce_bounds_module(pym)(self.lb, self.ub)
            s_physical = self._pin(self._filter(self.s_x))
            s_stiffness = pym.MathExpression(
                f"{scenario.Emin} + inp0^{settings['penal']}*({scenario.E0}-{scenario.Emin})"
            )(s_physical)
            s_K = pym.AssembleStiffness(domain, bc=fixed, e_modulus=1.0,
                                        poisson_ratio=scenario.nu, plane="stress")(s_stiffness)
            s_mass = modules["mass"](settings["low_density_below"], settings["low_density_exponent"])(s_physical)
            s_M = pym.AssembleMass(domain, bc=fixed, ndof=2, material_property=settings["mass_density"],
                                   bcdiagval=0.0, add_constant=diags(attached))(s_mass)
            self.s_eigenvalues, _ = modules["eigen"](hermitian=True, nmodes=int(values["modes"]), sigma=0.0)(s_K, s_M)
            self.s_objective = modules["minimum"](values["p"])(self.s_eigenvalues)
            self.s_volume = pym.EinSum("i->")(s_physical)

    def evaluate(self, x, gradients=True):
        self.s_x.state = np.asarray(x, dtype=float)
        self.network.response()
        gradient = self._gradient if gradients else (lambda response: None)
        eigenvalues = np.asarray(self.s_eigenvalues.state, dtype=float)
        return Evaluation(
            objective=float(self.s_objective.state),
            objective_gradient=gradient(self.s_objective),
            volume=self.s_volume.state,
            volume_gradient=gradient(self.s_volume),
            constraints=(),
            reported={f"omega_{i + 1}": float(np.sqrt(max(v, 0.0))) for i, v in enumerate(eigenvalues[:2])},
        )
