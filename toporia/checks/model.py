# checks/model.py — is a model (or a physics engine, through a model) sound?
#
# Bounds and shapes; volume_of agrees with evaluate; values without gradients
# equal values with them; every gradient against central finite differences.


import numpy as np

from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import make_problem

from .common import (
    WITH_HOLES,
    check_declaration,
    gradient_check,
    in_dims,
    random_design,
    small_run,
)
from .report import Check, Report

# ── Model and Physics ─────────────────────────────────────────────────────────

def _model_run(cls, problem=WITH_HOLES):
    """A run that makes the model compute its objective and, if it can, one constraint."""
    from toporia.plugins.responses import RESPONSES
    capabilities = cls.capabilities
    objective = "compliance" if "compliance" in capabilities.objectives else capabilities.objectives[0]
    constraints = []
    if capabilities.constraints and capabilities.max_constraints != 0:
        response = RESPONSES.get(capabilities.constraints[0])
        constraints = [{"type": response.name, **getattr(response, "gradient_check_settings", {})}]
    return in_dims(small_run(problem, m=0.3, volfrac=0.4, objective={"type": objective}, constraints=constraints),
                   capabilities.dims)


def check_model(cls):
    """Check a Model: shapes and bounds, consistency, and every gradient by finite differences."""
    report = Report(f"model {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    if not report.ok:
        return report
    run = _model_run(cls)
    problem = make_problem(run.scenario, run.solver.m)
    model = cls()
    with report.step(f"initialize on a problem with holes ({problem.dims}-D)") as check:
        model.initialize(problem, run.solver, resolve_params(cls.name, cls.params, {}))
        check.detail = (f"objective {run.scenario.objective['type']}, constraints "
                        f"{[c['type'] for c in run.scenario.constraints] or 'none'}")
    if not report.ok:
        return report

    with report.step("bounds, start design and physical density"):
        lower, upper = model.bounds()
        x0 = np.asarray(model.initial_design())
        assert np.shape(lower) == np.shape(upper) == x0.shape, "bounds and start design differ in shape"
        assert np.all(lower <= upper), "a lower bound exceeds its upper bound"
        assert np.all(x0 >= lower - 1e-12) and np.all(x0 <= upper + 1e-12), "the start design is out of bounds"
        density = model.physical(x0)
        assert density.shape == problem.shape, f"physical() returned shape {density.shape}"
        assert density.min() >= -1e-9 and density.max() <= 1 + 1e-9, "physical density outside [0, 1]"

    x = random_design(model)
    with report.step("evaluate: values with and without gradients agree"):
        full = model.evaluate(x)
        light = model.evaluate(x, gradients=False)
        assert light.objective == full.objective, "the objective changes when gradients are skipped"
        assert len(light.constraints) == len(full.constraints) == len(run.scenario.constraints), \
            "the number of constraints does not match the scenario"
        assert light.objective_gradient is None, "gradients=False still returned an objective gradient"
        assert np.isclose(model.volume_of(x), full.volume, rtol=1e-10), "volume_of disagrees with evaluate().volume"
    if not report.ok:
        return report

    movable = upper > lower
    gradient_check(lambda y: model.evaluate(y, gradients=False).objective, full.objective_gradient,
                    x, movable, report, "objective gradient vs finite differences")
    gradient_check(lambda y: model.evaluate(y, gradients=False).volume, full.volume_gradient,
                    x, movable, report, "volume gradient vs finite differences")
    for i, constraint in enumerate(full.constraints):
        gradient_check(lambda y, i=i: model.evaluate(y, gradients=False).constraints[i].value,
                        constraint.gradient, x, movable, report,
                        f"constraint {i} ({constraint.name}) gradient vs finite differences")
    return report


def check_physics(cls):
    """Check a Physics engine by checking a model assembled on it."""
    from toporia.plugins.models.assembled import AssembledModel
    model = type(f"{cls.__name__}Model", (AssembledModel,),
                 {"name": f"checked_{cls.name}", "label": cls.label, "physics": cls})
    report = check_model(model)
    report.subject = f"physics {cls.__name__} ({cls.name}), through an assembled model"
    report.checks.insert(0, Check("provides", True, ", ".join(cls.provides) or "nothing"))
    return report
