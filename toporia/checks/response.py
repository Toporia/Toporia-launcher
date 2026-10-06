# checks/response.py — is a response sound?
#
# Its roles, and its gradient against finite differences on every physics
# engine that provides the features it requires.


import numpy as np

from toporia.framework.params import resolve_params
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE
from toporia.framework.problem.mesh import RectangularProblem

from .common import (
    WITH_HOLES,
    check_declaration,
    gradient_check,
    small_run,
)
from .report import Report

# ── Response ──────────────────────────────────────────────────────────────────

def check_response(cls):
    """Check a Response: its roles, and its gradient on every engine that can compute it."""
    from toporia.plugins.models import MODELS
    from toporia.plugins.models.assembled import AssembledModel
    report = Report(f"response {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    with report.step("roles") as check:
        assert set(cls.roles) <= {OBJECTIVE_ROLE, CONSTRAINT_ROLE} and cls.roles, f"roles {cls.roles}"
        check.detail = ", ".join(cls.roles)
    if cls.requires is None:
        report.add("gradient vs finite differences", None, "declaration only: computed by a model that names it")
        return report

    engines = [model for model in MODELS.classes()
               if issubclass(model, AssembledModel) and cls.computable_on(model.physics)]
    if not engines:
        report.add("gradient vs finite differences", None, f"no registered engine provides {cls.requires}")
    for model_cls in engines:
        run = small_run(WITH_HOLES, m=0.3, volfrac=0.4)
        problem = RectangularProblem(run.scenario, run.solver.m)
        engine = model_cls.physics()
        engine.initialize(problem, resolve_params(model_cls.name, model_cls.params, {}))
        response = cls()
        response.setup(engine, problem, resolve_params(cls.name, cls.params,
                                                       getattr(cls, "gradient_check_settings", {})))
        rng = np.random.default_rng(1)
        density = np.clip(rng.uniform(0.2, 0.9, (problem.nely, problem.nelx)),
                          problem.lower_bound, problem.upper_bound)
        result = response.evaluate(engine.solve(density))
        with report.step(f"on {model_cls.label}: value without the gradient is the same"):
            assert response.evaluate(engine.solve(density), gradient=False).value == result.value
        gradient_check(lambda d, r=response, e=engine: r.evaluate(e.solve(d), gradient=False).value,
                        result.gradient, density, problem.upper_bound > problem.lower_bound, report,
                        f"on {model_cls.label}: gradient vs finite differences")
    return report
