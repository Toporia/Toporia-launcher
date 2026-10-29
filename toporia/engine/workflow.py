"""Execute nested workflows; parallel describes dependency, not thread scheduling."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from toporia.framework.problem.mesh import make_problem, projection
from toporia.framework.problem.workflow import stage_run, validate_workflow

from .loop import run_single_with_store
from .records import ResultStore, run_record


def combine(fields, operation):
    """Boolean operations on registered, same-mesh, completed designs at 0.5."""
    if len(fields) < 2 or len({np.shape(field) for field in fields}) != 1:
        raise ValueError("Boolean combination requires at least two designs on the same mesh")
    solid = [np.asarray(field) >= .5 for field in fields]
    if operation == "union":
        result = np.logical_or.reduce(solid)
    elif operation == "intersection":
        result = np.logical_and.reduce(solid)
    elif operation == "difference":
        result = solid[0] & ~np.logical_or.reduce(solid[1:])
    else:
        raise ValueError(f"Unknown Boolean operation: {operation}")
    return result.astype(float)


def restrict_problem(run, allowed):
    """Make void bounds enforce the preceding volume throughout the next solve."""
    from toporia.framework.parts.composition import ComposedMethod
    from toporia.plugins.methods import method_class

    cls = method_class(run.solver.method)
    if not issubclass(cls, ComposedMethod) or run.solver.representation.get("type", "element_density") != "element_density" or run.solver.variants:
        raise ValueError("Previous-volume restriction initially supports composed methods with element densities and no variants")
    problem = make_problem(run.scenario, run.solver.m)
    allowed = np.asarray(allowed, dtype=bool)
    if allowed.shape != problem.shape:
        raise ValueError("Sequential stages must share the same physical mesh")
    if not allowed.any():
        raise ValueError("The preceding optimized volume is empty")
    if np.any(problem.passive_elements & ~allowed):
        raise ValueError("The preceding volume removes mandatory solid regions")
    problem.void_elements |= ~allowed
    if np.sum(problem.lower_bound) > run.scenario.volfrac * allowed.sum():
        raise ValueError("Material budget within the preceding volume is smaller than mandatory solid regions")
    # Existing solvers measure volume against the complete rectangular mesh.
    scenario = replace(run.scenario, volfrac=run.scenario.volfrac * float(allowed.mean()))
    run = replace(run, scenario=scenario)
    problem.scenario = scenario
    return run, problem


def execution_problems(base, tree):
    """Explain unsupported restricted stages before any expensive solve starts."""
    from toporia.framework.parts.composition import ComposedMethod
    from toporia.plugins.methods import method_class
    issues = []

    def check(node, restricted=False):
        if node["kind"] == "optimization":
            run = stage_run(base, node)
            if restricted and (not issubclass(method_class(run.solver.method), ComposedMethod)
                               or run.solver.representation.get("type", "element_density") != "element_density"
                               or run.solver.variants):
                issues.append(f"{node['name']}: previous-volume restriction requires a composed method with element densities and no variants")
        else:
            for i, child in enumerate(node["children"]):
                check(child, restricted or (node["kind"] == "sequential" and i > 0))
    check(tree)
    return issues


def execute_workflow(base, tree, on_iteration=None, on_stage=None):
    """Finish independent branches, then combine. No per-iteration coupling."""
    validate_workflow(tree)
    issues = execution_problems(base, tree)
    if issues:
        raise ValueError("\n".join(issues))
    folder = Path(base.output.dir)
    folder.mkdir(parents=True, exist_ok=True)
    records = []

    def execute(node, allowed=None):
        kind = node["kind"]
        if kind == "optimization":
            run = stage_run(base, node).with_output_dir(folder / node["id"])
            run = replace(run, output=replace(run.output, postprocess=[]))
            problem = None
            if allowed is not None:
                run, problem = restrict_problem(run, allowed)
            if on_stage:
                on_stage(node, run)
            store, density = run_single_with_store(run, on_iteration, problem=problem)
            np.save(store.output_dir / "design.npy", density)
            store.save_history()
            if allowed is not None:
                if np.any(density[~allowed] > 1e-8):
                    raise ValueError("The selected method returned material outside its restricted domain")
                np.save(store.output_dir / "allowed_domain.npy", allowed)
            records.append({"id": node["id"], "name": node["name"], "folder": node["id"],
                            "objective": run.scenario.objective, "objectives": store.objectives,
                            "iterations": len(store.objectives), "max_iterations": run.solver.max_iter})
            return density, run, store.objectives, store.volumes
        if kind == "sequential":
            current = allowed
            result = None
            for child in node["children"]:
                result = execute(child, current)
                current = result[0] >= .5
            return result
        # Both branches receive the same input. Scheduling them consecutively
        # limits peak memory; neither branch consumes the other's output.
        outputs = [execute(child, allowed) for child in node["children"]]
        return combine([value[0] for value in outputs], node.get("operation", "union")), base, [], []

    density, final_run, objectives, volumes = execute(tree)
    store = ResultStore(folder)
    store.save_density(density, folder / "final_density.png")
    if density.ndim == 3:
        np.save(folder / "final_density.npy", density)
    path = folder / "design.npy"
    np.save(path, density)
    total = sum(record["iterations"] for record in records)
    value = f"{objectives[-1]:.6g}" if objectives else "not evaluated"
    np.savetxt(folder / "final_density.csv", np.flipud(projection(density)), delimiter=",",
               header=f"iterations,{total}\nobjective,{value}", comments="")
    record = run_record(final_run, iterations=total, stop_reason="workflow completed", responses={})
    record["workflow"] = {"definition": tree, "stages": records,
                          "scheduling": "independent branches finish before Boolean combination"}
    # A Boolean shape has no single physical objective/feasibility evaluation.
    record["result"]["feasible"] = None
    record["result"]["evaluation"] = "Combined result has not been re-analysed" if not objectives else "See final stage history"
    (folder / "run.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"kind": "density", "path": str(path), "folder": str(folder), "objectives": objectives,
            "volumes": volumes, "iteration": len(objectives) if objectives else total,
            "total_iterations": total, "objective_label": "Boolean combination (not evaluated)" if not objectives else None,
            "max_iterations": final_run.solver.max_iter if objectives else sum(r["max_iterations"] for r in records),
            "workflow": True}
