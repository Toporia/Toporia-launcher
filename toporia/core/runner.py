# runner.py — shared single-run helper used by all analysis scripts
#
# Kept in one place so Compare_Two, Sensitivity, SensitivitySweep, etc.
# can import rather than copy-paste the same loop.

import time

from toporia.methods import make_method
from .problem import RectangularProblem
from .results import ResultStore


def run_single(cfg, on_iteration=None):
    """Run one topology-optimisation pass to convergence.

    Parameters
    ----------
    cfg          : TopOptConfig
    on_iteration : callable, optional
        Called after every solver step as ``on_iteration(density, objectives, iteration)``.
        Raise an exception inside the callback to interrupt the loop early.

    Returns
    -------
    density : np.ndarray, shape (nely, nelx)
        Final density field, values in [0, 1].
    """
    method = make_method(cfg.method)
    method.initialize(RectangularProblem(cfg), cfg)
    store = ResultStore(cfg.output_dir)
    obj0  = None

    while not method.has_converged():
        t0 = time.perf_counter()
        method.step()
        d, it, obj = method.get_density(), method.get_iteration(), method.get_objective()
        if obj0 is None:
            obj0 = obj
        store.record(iteration=it, objective=obj, volume=float(d.mean()),
                     density=d, save_every=cfg.save_every)
        print(f"  it={it:03d}  obj={obj - obj0:+.4e}  vol={d.mean():.3f}"
              f"  t={time.perf_counter() - t0:.2f}s")
        if on_iteration:
            on_iteration(d, store.objectives, it)

    store.save_final(method.get_density(), save_history=False)
    return method.get_density()
