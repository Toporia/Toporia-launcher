# framework/companions.py — more physics on the same design field (To do item 9).
#
# A scenario can name physics besides the main one, each with its own material law:
#
#     extra_physics = [{"model": "q4_heat", "interpolation": {"type": "simp", "penal": 3.0},
#                       "E0": 1.0, "Emin": 1e-3}]
#
# E0 and Emin are this physics' own solid and void property (a conductivity for heat);
# without them E0 is the scenario's, and Emin the scenario's for elasticity but a
# thousandth of E0 for conduction (the heat-sink convention), since the elastic void of
# 1e-9 would make every cut heat path an almost perfect insulator.
#
# Every one is solved on the same physical density as the main physics, only when a
# variable asks for it, and at most once per design.  A measured variable says which
# physics it is measured on:
#
#     variables = [{"name": "heat", "type": "thermal_compliance", "physics": "q4_heat"}]
#
# and from there it becomes an objective, a term of a combined objective or a constraint
# (framework/variables.py, the "variable" response).  The physics are combined through the
# objective, not coupled: one field does not feed another (that is "coupled solving",
# To do section 6).
#
#   check_extra_physics   validate the specs against the main physics
#   build_companions      one Companion per spec, attached to the main engine
#   Companion             an engine, its material law, and its last solve


import numpy as np


def check_extra_physics(specs, main_model=None):
    """Validate extra physics specs; returns [(model class, interpolation spec)]."""
    from toporia_core.framework.parts.assembled import AssembledModel
    from toporia_core.framework.registries import MODELS
    found, seen = [], set()
    for spec in specs or ():
        if not isinstance(spec, dict) or "model" not in spec:
            raise ValueError(f"Every extra physics needs a 'model', got {spec!r}")
        unknown = set(spec) - {"model", "interpolation", "E0", "Emin"}
        if unknown:
            raise ValueError(f"An extra physics has no field(s) {sorted(unknown)}; it has 'model', "
                             f"'interpolation', 'E0' and 'Emin'")
        for key in ("E0", "Emin"):
            if key in spec and not (isinstance(spec[key], (int, float)) and spec[key] > 0):
                raise ValueError(f"An extra physics' {key} must be a positive number, got {spec[key]!r}")
        cls = MODELS.get(spec["model"])
        if not (isinstance(cls, type) and issubclass(cls, AssembledModel) and cls.physics is not None):
            raise ValueError(f"{cls.label!r} computes its own responses and cannot be an extra physics")
        if spec["model"] in seen or (main_model is not None and spec["model"] == main_model.name):
            raise ValueError(f"The physics {spec['model']!r} is named twice")
        if main_model is not None:
            dims = set(getattr(main_model.physics, "dims", (2,)))
            if not dims & set(getattr(cls.physics, "dims", (2,))):
                raise ValueError(f"{cls.label!r} does not work in the dimensions of {main_model.label!r}")
        seen.add(spec["model"])
        found.append((cls, dict(spec.get("interpolation") or {"type": "simp"}),
                      {key: float(spec[key]) for key in ("E0", "Emin") if key in spec}))
    return found


class Companion:
    """One more physics on the design field: solved on demand, once per design."""

    def __init__(self, model_cls, interpolation, problem, constants=None):
        from toporia_core.framework.params import resolve_params
        from toporia_core.framework.parts.assembled import material_law
        from toporia_core.framework.problem.solver import Solver
        self.name, self.label = model_cls.name, model_cls.physics.label
        problem = own_constants(problem, model_cls.physics, constants or {})
        self.problem = problem
        self.engine = model_cls.physics()
        self.material = None
        if model_cls.physics.uses_interpolation:
            self.material = material_law(Solver(interpolation=interpolation))
            reasons = self.material.problems_with(model_cls.physics)
            if reasons:
                raise ValueError(f"{self.label}: " + "; ".join(reasons))
            self.material.setup(problem)
        self.engine.initialize(problem, resolve_params(model_cls.name, model_cls.params, {}), self.material)
        self._density, self._state = None, None

    def solve(self, density):
        """The state for this density; solved again only when the density changed."""
        if self._density is None or self._density.shape != density.shape or not np.array_equal(self._density, density):
            self._state = self.engine.solve(density)
            self._density = np.array(density, copy=True)
        return self._state


def build_companions(specs, main_model, problem):
    """{model name: Companion} for a scenario's extra physics."""
    return {cls.name: Companion(cls, interpolation, problem, constants)
            for cls, interpolation, constants in check_extra_physics(specs, main_model)}


def own_constants(problem, physics, constants):
    """The problem with this physics' own solid and void property (see the header)."""
    import dataclasses

    from toporia_core.framework.parts.physics import THERMAL_ENERGY
    scenario = problem.scenario
    E0 = constants.get("E0", scenario.E0)
    default_void = 1e-3 * E0 if THERMAL_ENERGY in getattr(physics, "provides", ()) else scenario.Emin
    Emin = constants.get("Emin", default_void)
    if (E0, Emin) == (scenario.E0, scenario.Emin):
        return problem
    return dataclasses.replace(problem, scenario=dataclasses.replace(scenario, E0=E0, Emin=Emin))


class OnCompanion:
    """A response computed on a companion physics instead of the main one."""

    def __init__(self, response, companion):
        self.response, self.companion = response, companion
        self.name, self.label = response.name, f"{response.label} on {companion.label}"

    def evaluate(self, state, gradient=True):
        """Solve the companion on this state's density, then evaluate there."""
        return self.response.evaluate(self.companion.solve(state.density), gradient=gradient)


def set_up_response(cls, values, physics, problem, on=None):
    """Set a response up on the main physics, or on the companion named `on`."""
    if on is None:
        response = cls()
        response.setup(physics, problem, values)
        return response
    companions = getattr(physics, "companions", None) or {}
    if on not in companions:
        named = ", ".join(companions) or "none"
        raise ValueError(f"There is no extra physics {on!r} on this problem (extra physics: {named}); "
                         f"add it on the Problem page")
    companion = companions[on]
    if not cls.computable_on(type(companion.engine)):
        raise ValueError(f"{cls.label!r} cannot be computed on {companion.label!r}")
    response = cls()
    response.setup(companion.engine, problem, values)
    return OnCompanion(response, companion)
