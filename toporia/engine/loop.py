# engine/runner.py — the optimisation loop.
#
# Every analysis mode (run_one, sweep, compare, sensitivity) goes through this
# module, so the wiring, the loop, the stopping rule and the recording all live
# in one place:
#
#     Run.scenario ──(Run.solver.m)──> RectangularProblem ──┐
#     Run.solver ───────────────────────────────────────────┴─> method.initialize(problem, solver)
#                                                                  │
#     for each iteration:  method.step(i) → density, responses, change
#                          record · live callback · stopping rule
#                                                                  │
#     after the loop:      every limit checked; broken ones printed as WARNINGs
#                                                                  │
#     Run.output.dir  <── final_density.png/.csv, run.json (provenance + limits)
#
# The engine owns the iteration counter and the stopping decision.  A method
# reports how far the design moved; the engine decides whether that is small
# enough to stop.  That is what makes two different algorithms comparable: both
# are held to the same tolerance, and the reason a run ended is recorded.

import time

from toporia.framework.parts.method import OBJECTIVE
from toporia.framework.problem.mesh import RectangularProblem
from toporia.framework.registry import install_hint, missing_dependencies

from .pipeline import describe_pipeline
from .records import ResultStore, check_limits, describe_violations, run_record


def initialized_method(run):
    """Check the method can solve the scenario, then build the problem and the method.

    The check comes first, so a scenario asking for something the method cannot
    do — a stress constraint with optimality criteria, say — fails immediately
    with a message naming the methods that can, instead of part-way through.
    """
    from toporia.plugins.methods import method_class, method_classes
    from toporia.plugins.responses import check_responses

    method_cls = method_class(run.solver.method)
    missing = missing_dependencies(method_cls)
    if missing:
        raise ImportError(f"Method {method_cls.name!r} needs {', '.join(missing)}, which is not installed. "
                          f"Install it with:  {install_hint(missing)}")
    reasons = method_cls.capabilities.problems_with(run.scenario)
    if reasons:
        able = [cls.name for cls in method_classes() if not cls.capabilities.problems_with(run.scenario)]
        advice = f"Methods that can: {able}." if able else "No registered method can."
        raise ValueError(f"Method {method_cls.name!r} cannot solve this scenario: "
                         f"{'; '.join(reasons)}. {advice}")
    (objective_cls, _), _ = check_responses(run.scenario)
    if objective_cls.advice:
        print(f"note: {objective_cls.advice}")
    print(f"  pipeline: {describe_pipeline(run)}")

    problem = RectangularProblem(run.scenario, run.solver.m)
    method = method_cls()
    method.initialize(problem, run.solver)
    view = method.describe_view() if hasattr(method, "describe_view") else None
    if view:
        print(f"  optimiser sees: {view}")
    return method


def run_single(run, on_iteration=None):
    """Run one pass to convergence and return the final density field.

    Thin wrapper over :func:`run_single_with_store` for the common case where
    only the design matters — sweeps, comparisons and sensitivity studies.
    """
    return run_single_with_store(run, on_iteration)[1]


def run_single_with_store(run, on_iteration=None):
    """Run one topology-optimisation pass to convergence.

    Parameters
    ----------
    run          : core.run.Run
    on_iteration : callable, optional
        Called after every solver step as ``on_iteration(density, objectives, iteration)``.
        Raise an exception inside the callback to interrupt the loop early.

    Returns
    -------
    (store, density) : (ResultStore, np.ndarray)
        The recorded history, and the final (nely, nelx) density field in [0, 1].
    """
    method = initialized_method(run)
    store = ResultStore(run.output.dir)
    try:
        iteration, stop_reason = _loop(run, method, store, on_iteration)
    finally:
        method.close()   # however the run ends: limit, tolerance, Stop button, error

    print(f"  stopped: {stop_reason}")
    optimiser = method.report()
    if optimiser:
        verdict = "finished" if optimiser.get("finished") else "did not finish"
        print(f"  optimiser {verdict}: {optimiser.get('message')}")
    final = {name: values[-1] for name, values in store.responses.items()}
    limits = check_limits(run.scenario, final)
    for line in describe_violations(limits):
        print(f"  WARNING: {line}")

    store.stop_reason = stop_reason
    store.limits = limits
    store.optimiser = optimiser
    store.save_final(method.get_density(), save_history=False)
    store.save_json("run.json", run_record(
        run, iterations=iteration, stop_reason=stop_reason, responses=final, limits=limits,
        optimiser=optimiser,
    ))
    return store, method.get_density()


def _loop(run, method, store, on_iteration):
    """The iterations themselves; returns (last iteration, stop reason)."""
    solver = run.solver
    obj0 = None
    iteration = 0
    stop_reason = f"iteration limit ({solver.max_iter})"
    for iteration in range(1, solver.max_iter + 1):
        t0 = time.perf_counter()
        method.step(iteration)

        responses = method.get_responses()
        objective = responses[OBJECTIVE]
        density = method.get_density()
        change = method.get_change()
        if obj0 is None:
            obj0 = objective

        store.record(iteration=iteration, objective=objective,
                     volume=float(density.mean()), density=density,
                     save_every=run.output.save_every, responses=responses)
        solves = f"  solves={responses['solves']:d}" if "solves" in responses else ""
        print(f"  it={iteration:03d}  obj={objective - obj0:+.4e}  vol={density.mean():.3f}"
              f"{solves}  t={time.perf_counter() - t0:.2f}s")
        if on_iteration:
            on_iteration(density, store.objectives, iteration)

        # Platform rule first: it applies to every method and is what keeps a
        # cross-method benchmark honest.
        if change < solver.tol:
            stop_reason = f"design change {change:.3g} < tol {solver.tol:g}"
            break
        # Escape hatch for criteria that cannot be written as a design change.
        if method.is_converged():
            stop_reason = (method.convergence_reason()
                           or f"{type(method).__name__} reported its own convergence criterion")
            break
    return iteration, stop_reason
