# apps/gui/preflight.py — actionable checks for a physical definition and method.
# A rigid-body rank test diagnoses missing supports; it does not claim that every
# disconnected design or future physics problem is well posed.

import math

from toporia.engine.pipeline import solver_problems
from toporia.framework.registry import missing_dependencies
from toporia.plugins.methods import method_class


def problems(run, check_mesh=False, mesh_limit=200_000):
    """Return errors without changing the project or silently supplying defaults."""
    try:
        method = method_class(run.solver.method)
        issues = method.capabilities.problems_with(run.scenario) + solver_problems(method, run)
        missing = missing_dependencies(method)
        if missing:
            issues.append(f"Install the optional dependencies for this method: {', '.join(missing)}")
        if run.scenario.regions is not None:
            from toporia.framework.problem.mesh import make_problem
            from toporia.framework.problem.regions import validate_scenario
            validate_scenario(run.scenario, run.solver.m)
            count = math.prod(max(1, round(size * run.solver.m)) for size in
                              (run.scenario.Lx, run.scenario.Ly, *([run.scenario.Lz] if run.scenario.Lz else [])))
            if check_mesh and (mesh_limit is None or count <= mesh_limit):
                from toporia.framework.problem.regions import validate_field
                # What a support and a load mean depends on what the physics solves.
                thermal = "thermal_compliance" in method.capabilities.objectives
                validate_field(make_problem(run.scenario, run.solver.m), "temperature" if thermal else "displacement")
            elif check_mesh:
                issues.append("Mesh exceeds 200,000 elements; full spatial validation runs when you press Run.")
        return issues
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return [str(error)]
