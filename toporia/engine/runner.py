# engine/runner.py — the optimisation loop.
#
# Every analysis mode (run_one, sweep, compare, sensitivity) goes through this
# one function, so the loop, the stopping rule and the recording all live in a
# single place.
#
# The engine owns the iteration counter and the stopping decision.  A method
# reports how far the design moved; the engine decides whether that is small
# enough to stop.  That is what makes two different algorithms comparable: both
# are held to the same tolerance, and the reason a run ended is recorded.

import time

from toporia.core.contract import OBJECTIVE
from toporia.core.problem import RectangularProblem

from .results import ResultStore


def run_single(cfg, on_iteration=None):
    """Run one pass to convergence and return the final density field.

    Thin wrapper over :func:`run_single_with_store` for the common case where
    only the design matters — sweeps, comparisons and sensitivity studies.
    """
    return run_single_with_store(cfg, on_iteration)[1]


def run_single_with_store(cfg, on_iteration=None):
    """Run one topology-optimisation pass to convergence.

    Parameters
    ----------
    cfg          : TopOptConfig
    on_iteration : callable, optional
        Called after every solver step as ``on_iteration(density, objectives, iteration)``.
        Raise an exception inside the callback to interrupt the loop early.

    Returns
    -------
    (store, density) : (ResultStore, np.ndarray)
        The recorded history, and the final (nely, nelx) density field in [0, 1].
    """
    from toporia.library.methods import make_method

    method = make_method(cfg.method)
    method.initialize(RectangularProblem(cfg), cfg)
    store = ResultStore(cfg.output_dir)
    obj0 = None
    stop_reason = f"iteration limit ({cfg.max_iter})"

    for iteration in range(1, cfg.max_iter + 1):
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
                     save_every=cfg.save_every, responses=responses)
        print(f"  it={iteration:03d}  obj={objective - obj0:+.4e}  vol={density.mean():.3f}"
              f"  t={time.perf_counter() - t0:.2f}s")
        if on_iteration:
            on_iteration(density, store.objectives, iteration)

        # Platform rule first: it applies to every method and is what keeps a
        # cross-method benchmark honest.
        if change < cfg.tol:
            stop_reason = f"design change {change:.3g} < tol {cfg.tol:g}"
            break
        # Escape hatch for criteria that cannot be written as a design change.
        if method.is_converged():
            stop_reason = f"{type(method).__name__} reported its own convergence criterion"
            break

    print(f"  stopped: {stop_reason}")
    store.stop_reason = stop_reason
    store.save_final(method.get_density(), save_history=False)
    return store, method.get_density()
