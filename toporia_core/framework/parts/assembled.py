# toporia_core/framework/parts/assembled.py — a model assembled from swappable parts.
#
# Every density model does the same five things, so they are written once:
#
#     z ──Representation──> x ──Filters──> ρ ──Physics.solve──> state ──Responses──> objective, constraints
#     dz <──backward─────── dx <─filter adjoint── dρ <─────────── gradients ─────────────┘
#
#   Representation  solver.representation         (toporia_library/representations): what the
#              design variables z are, and where they start; usually one density per element
#   Filters    solver.filter_specs                    (toporia_library/filters)
#   Material   solver.interpolation                   (toporia_library/interpolations), for an
#              engine that interpolates stiffness from density
#   Physics    the model's `physics` class            (toporia_core/framework/parts/physics.py, toporia_library/physics)
#   Responses  scenario.objective and .constraints    (toporia_library/responses)
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
#
# Several fields per element (Wave 5): a representation may describe more than the
# density (candidate-material weights, a fibre angle).  Each extra field goes to the one
# part that reads it, the material law or the physics, before every solve; the responses
# give d(value)/d(field) (field_gradient), the material law d(volume)/d(field), and the
# representation carries both back to the variables with backward_extra.  The filters act
# on the density only.

import re

import numpy as np

from toporia_core.framework.companions import build_companions
from toporia_core.framework.parts.filter_pipeline import DensityFilterPipeline
from toporia_core.framework.parts.method import Capabilities
from toporia_core.framework.parts.model import ConstraintValue, Evaluation, Model
from toporia_core.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE
from toporia_core.framework.parts.schedule import change_parameter
from toporia_core.framework.registries import RESPONSES, resolve_response, responses_for
from toporia_core.framework.variables import VariableSet


def _capabilities(physics):
    """What a model on this physics can minimise and constrain: every computable response."""
    def computable(role):
        """The responses in `role` this physics can compute."""
        return [cls for cls in responses_for(role) if cls.computable_on(physics)]
    objectives = computable(OBJECTIVE_ROLE)
    return Capabilities(variable_kind="density", accepts_filters=True,
                        accepts_interpolation=physics.uses_interpolation, accepts_representation=True,
                        dims=tuple(getattr(physics, "dims", (2,))),
                        supports_springs=getattr(physics, "supports_springs", False),
                        objectives=tuple(cls.name for cls in objectives),
                        constraints=tuple(cls.name for cls in computable(CONSTRAINT_ROLE)),
                        max_constraints=None,
                        needs_constraint=tuple(cls.name for cls in objectives if cls.needs_constraint),
                        updater_only=tuple((cls.name, tuple(cls.only_with_updaters))
                                           for cls in responses_for(CONSTRAINT_ROLE) + responses_for(OBJECTIVE_ROLE)
                                           if getattr(cls, "only_with_updaters", ())))


def material_law(solver):
    """The Interpolation named by solver.interpolation, with its parameters validated."""
    from toporia_core.framework.params import resolve_params
    from toporia_core.framework.registries import INTERPOLATIONS
    spec = dict(solver.interpolation)
    cls = INTERPOLATIONS.get(spec.pop("type", "simp"))
    return cls(**resolve_params(f"interpolation {cls.name!r}", cls.params, spec))


def design_representation(solver):
    """The Representation named by solver.representation, with its parameters validated."""
    from toporia_core.framework.params import resolve_params
    from toporia_core.framework.registries import REPRESENTATIONS
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
        if scenario.point_springs and not self.capabilities.supports_springs:
            raise ValueError(f"{type(self).__name__} does not support point springs")
        if getattr(problem, "region_springs", None) and not self.capabilities.supports_springs:
            raise ValueError(f"{self.label} does not support springs; choose a model with port springs "
                             f"(2-D Q4 elasticity with port springs)")
        self.problem = problem

        n_total = int(np.prod(problem.shape))
        n_passive = int(np.sum(problem.passive_elements))
        if n_passive > scenario.volfrac * n_total:
            raise ValueError(
                f"Infeasible volume fraction: passive (forced-solid) elements already "
                f"fill {n_passive / n_total:.1%} of the domain, which exceeds "
                f"volfrac={scenario.volfrac:.1%}. Raise volfrac or reduce the passive region."
            )

        self.engine = type(self).physics()
        self.material = material_law(solver) if self.physics.uses_interpolation else None
        if self.material is not None:
            reasons = self.material.problems_with(self.physics)
            if reasons:
                raise ValueError("; ".join(reasons))
            self.material.setup(problem)
        self.engine.initialize(problem, settings, self.material)
        # More physics on the same field, solved when a variable asks (toporia_core/framework/companions.py).
        self.engine.companions = build_companions(getattr(scenario, "extra_physics", None), type(self), problem)
        self.representation = design_representation(solver)
        self.representation.setup(problem)
        self.fields = tuple(getattr(self.representation, "fields", ()))
        self._check_fields()
        self.lb, self.ub = self.representation.bounds()
        self.volume_limit = scenario.volfrac * n_total
        self.pipeline = DensityFilterPipeline(problem, solver)
        self.monitor_physical_change = self.representation.monitor_physical_change or bool(
            self.pipeline.chain and any(f.calibrate_initial_volume for f in self.pipeline.chain.filters))

        self.objective = self._response(scenario.objective, OBJECTIVE_ROLE)
        self.constraints = [self._response(spec, CONSTRAINT_ROLE) for spec in scenario.constraints]
        # The scenario's own variables are recorded every iteration (toporia_core/framework/variables.py).
        self.variables = (VariableSet(self.engine, problem, scenario.variables)
                          if getattr(scenario, "variables", None) else None)
        # Compliance is worth recording whenever it is not the objective and
        # the engine gives it for free.
        self.compliance = None
        if self.objective.name != "compliance":
            compliance_cls = RESPONSES.get("compliance")
            if compliance_cls.computable_on(type(self).physics):
                self.compliance = compliance_cls()
                self.compliance.setup(self.engine, problem, {})

    def _check_fields(self):
        """Every extra field of the representation has exactly one reader: the material law or the physics.

        A reader without its field uses its default (one material, fibres along x).
        """
        made = set(self.fields)
        by_material = set(getattr(self.material, "fields", ()) or ()) if self.material is not None else set()
        by_physics = set(getattr(self.engine, "fields", ()) or ())
        unread = made - (by_material | by_physics)
        if unread or by_material & by_physics & made:
            raise ValueError(
                f"The design's extra fields {sorted(made)} need a reader: the material law reads "
                f"{sorted(by_material) or 'none'} and the physics {sorted(by_physics) or 'none'}; choose a "
                f"representation, material law and physics that belong together")
        self.fields = tuple(name for name in self.fields if name in by_material | by_physics)

    def _set_fields(self, z):
        """Hand the extra fields of design z to their readers."""
        if not self.fields:
            return
        values = self.representation.extra(z)
        if self.material is not None and getattr(self.material, "fields", ()):
            self.material.set_fields({name: values[name] for name in self.material.fields},
                                     order=getattr(self.engine, "element_order", "C"))
        if getattr(self.engine, "fields", ()):
            self.engine.set_fields({name: values[name] for name in self.engine.fields})

    def _field_backward(self, z, response, state):
        """d(response)/dz through the extra fields."""
        return self.representation.backward_extra(z, {name: response.field_gradient(state, name)
                                                      for name in self.fields})

    def _response(self, spec, role):
        cls, values = resolve_response(spec, role)
        if not cls.computable_on(type(self).physics):
            raise ValueError(f"{cls.label!r} cannot be computed on {type(self).physics.label!r}; "
                             f"it needs the physics features {cls.requires}")
        response = cls()
        response.role = role
        response.setup(self.engine, self.problem, values)
        if self.fields and not getattr(response, "handles_fields", False):
            raise ValueError(f"{cls.label!r} cannot be used with a design of several fields per element "
                             f"({', '.join(self.fields)}); compliance and thermal compliance can")
        return response

    def initial_design(self):
        design = self.representation.initial()
        chain = self.pipeline.chain
        nonlinear_volume = self.material is not None and self.material.nonlinear_volume
        calibrated_filter = chain is not None and any(f.calibrate_initial_volume for f in chain.filters)
        if not self.representation.element_wise or not (nonlinear_volume or calibrated_filter):
            return design
        # A cumulative shadow of a uniform gray source is almost all solid.
        # Start on the physical volume budget instead, without changing the
        # source scale or weakening the manufacturing equations. Fixed solids
        # (and their unavoidable shadows) must fit even at the lowest design.
        # A nonlinear volume law likewise starts within its effective budget.
        if self.volume_of(self.lb) > self.volume_limit + 1e-8:
            raise ValueError("Manufacturing-filter shadows of fixed solids exceed the volume budget")
        if self.volume_of(design) <= self.volume_limit:
            return design
        low, high = 0.0, 1.0
        for _ in range(50):
            mid = 0.5 * (low + high)
            if self.volume_of(self.lb + mid * (design - self.lb)) > self.volume_limit:
                high = mid
            else:
                low = mid
        return self.lb + low * (design - self.lb)

    def bounds(self):
        return self.lb, self.ub

    def physical(self, z):
        return self.pipeline.physical_density(self.representation.density(z))

    def volume_of(self, z):
        """Cheap budget evaluation, including a selected effective-volume law."""
        self._set_fields(z)
        rho = self.physical(z)
        return np.sum(self.material.volume_density(rho) if self.material is not None else rho)

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
        self._set_fields(z)
        state = self.engine.solve(x_phys)

        objective = self.objective.evaluate(state, gradient=gradients)
        # Gradients come back with respect to the physical density; the filter
        # pipeline's adjoint maps them to the element field, and the
        # representation's to the design variables.
        dc = dv = None
        if gradients:
            volume_slope = self.material.volume_slope(x_phys) if self.material is not None else np.ones_like(x)
            dc, dv = self.pipeline.sensitivities(objective.gradient, volume_slope)
            dc, dv = self._backward(z, dc), self._backward(z, dv)
            if self.fields:
                dc = dc + self._field_backward(z, self.objective, state)
                slopes = self.material.volume_field_slopes(x_phys) if self.material is not None else {}
                dv = dv + self.representation.backward_extra(
                    z, {name: slopes.get(name, np.zeros_like(self.representation.extra(z)[name]))
                        for name in self.fields})

        reported = dict(objective.reported)
        volume = np.sum(self.material.volume_density(x_phys) if self.material is not None else x_phys)
        if self.material is not None and self.material.nonlinear_volume:
            reported.update(geometric_volume_fraction=float(np.mean(x_phys)),
                            effective_volume_fraction=float(volume / x_phys.size))
        constraints = []
        for i, response in enumerate(self.constraints):
            result = response.evaluate(state, gradient=gradients)
            gradient = self._backward(z, self.pipeline.sensitivity(result.gradient)) if gradients else None
            if gradients and self.fields:
                gradient = gradient + self._field_backward(z, response, state)
            constraints.append(ConstraintValue(response.name, result.value, gradient, exact=result.exact))
            for key, value in result.reported.items():
                reported[key if len(self.constraints) == 1 else f"{key}_{i}"] = value
        if self.compliance is not None:
            reported["compliance"] = self.compliance.evaluate(state, gradient=False).value
        if self.variables is not None:
            for name, (value, _) in self.variables.evaluate(state).items():
                if name in self.variables.names:
                    reported[f"var:{name}"] = value

        return Evaluation(objective=objective.value, objective_gradient=dc,
                          volume=volume, volume_gradient=dv,
                          constraints=tuple(constraints), reported=reported)

    def advance(self, completed):
        self.pipeline.step(completed)

    def continuing(self):
        return self.pipeline.chain is not None and self.pipeline.chain.continuing()

    def geometry(self, z):
        return self.representation.outlines(z)

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
