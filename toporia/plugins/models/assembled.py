# library/models/assembled.py — a model assembled from swappable parts.
#
# Every density model does the same four things, so they are written once:
#
#     x ──Filters──> ρ ──Physics.solve──> state ──Responses──> objective, constraints
#     dx <─filter adjoint── dρ <─────────── gradients ─────────────┘
#
#   Filters    solver.filter_specs                    (library/filters)
#   Physics    the model's `physics` class            (core/physics.py, library/fe)
#   Responses  scenario.objective and .constraints    (library/responses)
#
# A new physics engine becomes a model with one declaration:
#
#     class Q4Model(AssembledModel):
#         name, label = "q4", "2-D Q4 plane stress (Toporia)"
#         physics = Q4PlaneStress
#
# and it can then minimise or constrain every response its engine provides the
# features for — compliance, volume, stress — with every filter and every
# updater.  A new response or filter likewise works with every engine.

import numpy as np

from toporia.framework.parts.method import Capabilities
from toporia.framework.parts.model import ConstraintValue, Evaluation, Model
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE
from toporia.plugins.filters.pipeline import DensityFilterPipeline
from toporia.plugins.responses import RESPONSES, resolve_response, responses_for


def _capabilities(physics):
    """What a model on this physics can minimise and constrain: every computable response."""
    def computable(role):
        return [cls for cls in responses_for(role) if cls.computable_on(physics)]
    objectives = computable(OBJECTIVE_ROLE)
    return Capabilities(variable_kind="density", accepts_filters=True,
                        objectives=tuple(cls.name for cls in objectives),
                        constraints=tuple(cls.name for cls in computable(CONSTRAINT_ROLE)),
                        max_constraints=None,
                        needs_constraint=tuple(cls.name for cls in objectives if cls.needs_constraint))


class AssembledModel(Model):
    """Filters, a physics engine and the scenario's responses, joined into a Model.

    Subclasses set `physics` (a core.physics.Physics class) and their registry
    name and label.  Parameters and capabilities follow from the engine.
    """

    physics = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.physics is None:
            return
        cls.params = tuple(cls.physics.params)
        cls.capabilities = _capabilities(cls.physics)

    def initialize(self, problem, solver, settings):
        scenario = problem.scenario
        self.problem = problem

        n_total = problem.nelx * problem.nely
        n_passive = int(np.sum(problem.passive_elements))
        if n_passive > scenario.volfrac * n_total:
            raise ValueError(
                f"Infeasible volume fraction: passive (forced-solid) elements already "
                f"fill {n_passive / n_total:.1%} of the domain, which exceeds "
                f"volfrac={scenario.volfrac:.1%}. Raise volfrac or reduce the passive region."
            )

        self.engine = type(self).physics()
        self.engine.initialize(problem, settings)
        self.lb, self.ub = problem.lower_bound, problem.upper_bound
        self.volume_limit = scenario.volfrac * n_total
        self.pipeline = DensityFilterPipeline(problem, solver)

        self.objective = self._response(scenario.objective, OBJECTIVE_ROLE)
        self.constraints = [self._response(spec, CONSTRAINT_ROLE) for spec in scenario.constraints]
        # Compliance is worth recording whenever it is not the objective and
        # the engine gives it for free.
        self.compliance = None
        if self.objective.name != "compliance":
            compliance_cls = RESPONSES.get("compliance")
            if compliance_cls.computable_on(type(self).physics):
                self.compliance = compliance_cls()
                self.compliance.setup(self.engine, problem, {})

    def _response(self, spec, role):
        cls, values = resolve_response(spec, role)
        if not cls.computable_on(type(self).physics):
            raise ValueError(f"{cls.label!r} cannot be computed on {type(self).physics.label!r}; "
                             f"it needs the physics features {cls.requires}")
        response = cls()
        response.setup(self.engine, self.problem, values)
        return response

    def initial_design(self):
        problem = self.problem
        full = np.full((problem.nely, problem.nelx), problem.scenario.volfrac)
        return np.clip(full, self.lb, self.ub)

    def bounds(self):
        return self.lb, self.ub

    def physical(self, x):
        return self.pipeline.physical_density(x)

    def evaluate(self, x, gradients=True):
        x_phys = self.physical(x)
        state = self.engine.solve(x_phys)

        objective = self.objective.evaluate(state, gradient=gradients)
        # Gradients come back with respect to the physical density; the filter
        # pipeline's adjoint maps them to the design.
        dc = dv = None
        if gradients:
            dc, dv = self.pipeline.sensitivities(objective.gradient, np.ones_like(x))

        reported = dict(objective.reported)
        constraints = []
        for i, response in enumerate(self.constraints):
            result = response.evaluate(state, gradient=gradients)
            gradient = self.pipeline.sensitivity(result.gradient) if gradients else None
            constraints.append(ConstraintValue(response.name, result.value, gradient, exact=result.exact))
            for key, value in result.reported.items():
                reported[key if len(self.constraints) == 1 else f"{key}_{i}"] = value
        if self.compliance is not None:
            reported["compliance"] = self.compliance.evaluate(state, gradient=False).value

        return Evaluation(objective=objective.value, objective_gradient=dc,
                          volume=np.sum(x_phys), volume_gradient=dv,
                          constraints=tuple(constraints), reported=reported)

    def advance(self, completed):
        self.pipeline.step(completed)
