# plugins/models/assembled.py — a model assembled from swappable parts.
#
# Every density model does the same five things, so they are written once:
#
#     z ──Representation──> x ──Filters──> ρ ──Physics.solve──> state ──Responses──> objective, constraints
#     dz <──backward─────── dx <─filter adjoint── dρ <─────────── gradients ─────────────┘
#
#   Representation  solver.representation         (plugins/representations): what the
#              design variables z are, and where they start; usually one density per element
#   Filters    solver.filter_specs                    (plugins/filters)
#   Material   solver.interpolation                   (plugins/interpolations), for an
#              engine that interpolates stiffness from density
#   Physics    the model's `physics` class            (framework/parts/physics.py, plugins/physics)
#   Responses  scenario.objective and .constraints    (plugins/responses)
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

import re

import numpy as np

from toporia.framework.parts.method import Capabilities
from toporia.framework.parts.model import ConstraintValue, Evaluation, Model
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE
from toporia.framework.parts.schedule import change_parameter
from toporia.plugins.filters.pipeline import DensityFilterPipeline
from toporia.plugins.responses import RESPONSES, resolve_response, responses_for


def _capabilities(physics):
    """What a model on this physics can minimise and constrain: every computable response."""
    def computable(role):
        """The responses in `role` this physics can compute."""
        return [cls for cls in responses_for(role) if cls.computable_on(physics)]
    objectives = computable(OBJECTIVE_ROLE)
    return Capabilities(variable_kind="density", accepts_filters=True,
                        accepts_interpolation=physics.uses_interpolation, accepts_representation=True,
                        objectives=tuple(cls.name for cls in objectives),
                        constraints=tuple(cls.name for cls in computable(CONSTRAINT_ROLE)),
                        max_constraints=None,
                        needs_constraint=tuple(cls.name for cls in objectives if cls.needs_constraint))


def material_law(solver):
    """The Interpolation named by solver.interpolation, with its parameters validated."""
    from toporia.framework.params import resolve_params
    from toporia.plugins.interpolations import INTERPOLATIONS
    spec = dict(solver.interpolation)
    cls = INTERPOLATIONS.get(spec.pop("type", "simp"))
    return cls(**resolve_params(f"interpolation {cls.name!r}", cls.params, spec))


def design_representation(solver):
    """The Representation named by solver.representation, with its parameters validated."""
    from toporia.framework.params import resolve_params
    from toporia.plugins.representations import REPRESENTATIONS
    spec = dict(solver.representation)
    cls = REPRESENTATIONS.get(spec.pop("type", "element_density"))
    return cls(**resolve_params(f"representation {cls.name!r}", cls.params, spec))


class AssembledModel(Model):
    """Filters, a physics engine and the scenario's responses, joined into a Model.

    Subclasses set `physics` (a framework.parts.physics.Physics class) and their registry
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
        self.engine.initialize(problem, settings, material_law(solver) if self.physics.uses_interpolation else None)
        self.representation = design_representation(solver)
        self.representation.setup(problem)
        self.lb, self.ub = self.representation.bounds()
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
        return self.representation.initial()

    def bounds(self):
        return self.lb, self.ub

    def physical(self, z):
        return self.pipeline.physical_density(self.representation.density(z))

    def _backward(self, z, sensitivity):
        """A sensitivity w.r.t. the element field x, carried back to the variables z."""
        if self.representation.element_wise:
            return sensitivity
        # Elements in holes and solid rings are overwritten after filtering; with
        # element densities the flat view leaves them out, here they must not
        # steer the variables either.
        return self.representation.backward(z, np.where(self.pipeline.pinned, 0.0, sensitivity))

    def evaluate(self, z, gradients=True):
        x = self.representation.density(z)
        x_phys = self.pipeline.physical_density(x)
        state = self.engine.solve(x_phys)

        objective = self.objective.evaluate(state, gradient=gradients)
        # Gradients come back with respect to the physical density; the filter
        # pipeline's adjoint maps them to the element field, and the
        # representation's to the design variables.
        dc = dv = None
        if gradients:
            dc, dv = self.pipeline.sensitivities(objective.gradient, np.ones_like(x))
            dc, dv = self._backward(z, dc), self._backward(z, dv)

        reported = dict(objective.reported)
        constraints = []
        for i, response in enumerate(self.constraints):
            result = response.evaluate(state, gradient=gradients)
            gradient = self._backward(z, self.pipeline.sensitivity(result.gradient)) if gradients else None
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

    def continuing(self):
        return self.pipeline.chain is not None and self.pipeline.chain.continuing()

    def set_parameter(self, path, value):
        """Change a value of a live part: the material law, the representation, a filter, a response."""
        name = path.rpartition(".")[2]
        change_parameter(self._part_at(path), name, value)

    def _part_at(self, path):
        prefix, _, _ = path.rpartition(".")
        if prefix == "interpolation" and self.physics.uses_interpolation:
            return self.engine.material
        if prefix == "representation":
            return self.representation
        if prefix == "objective":
            return self.objective
        indexed = re.fullmatch(r"(filters|constraints)\[(\d+)\]", prefix)
        if indexed and indexed[1] == "filters" and self.pipeline.chain is not None:
            return self.pipeline.chain.filters[int(indexed[2])]
        if indexed and indexed[1] == "constraints":
            return self.constraints[int(indexed[2])]
        raise ValueError(f"{self.label} has no part at {path!r} that could change during a run")
