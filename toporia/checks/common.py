# checks/common.py — what every conformance check uses.
#
# The problems checks run on, a small run of the benchmark, stepping a method
# under the engine's stopping rule, comparing a gradient with central finite
# differences, and making sure no optimiser thread is left behind.

import contextlib
import threading

import numpy as np

from toporia.framework.params import resolve_params

from .report import Skip

#: Problems the checks run on: the classic benchmark, and one with holes and solid rings.
BENCHMARK, WITH_HOLES = "MBB Beam", "Drone Arm"



# ── Shared pieces ─────────────────────────────────────────────────────────────

def check_declaration(report, cls):
    """Every plugin: a name, a label, and parameters with unique names that resolve to their defaults."""
    with report.step("declaration: name, label and parameters") as check:
        assert getattr(cls, "name", ""), "name is empty, so the plugin cannot be registered"
        assert getattr(cls, "label", ""), "label is empty, so menus would show nothing"
        names = [p.name for p in cls.params]
        assert len(names) == len(set(names)), f"duplicate parameter names in {names}"
        resolve_params(cls.name, cls.params, {})
        check.detail = f"{len(names)} parameter(s)"


@contextlib.contextmanager
def registered(registry, cls):
    """Make `cls` reachable by name for the duration of a check, if it is not already."""
    known = cls.name in registry and registry.get(cls.name) is cls
    if not known:
        registry.register(cls)
    try:
        yield
    finally:
        if not known:
            registry.unregister(cls.name)


def small_run(problem=BENCHMARK, **values):
    """A preset run made small (mesh 0.4 el/mm unless given, no snapshots), with `values` applied."""
    from toporia.plugins.problems import get_run
    values.setdefault("m", 0.4)
    values.setdefault("save_every", 0)
    return get_run(problem).updated(**values)


def in_dims(run, dims):
    """`run` itself when a part working in `dims` can take a 2-D problem; else the same problem in 3-D.

    The 3-D version is the scenario extruded two elements deep, with the
    model q4 replaced by its 3-D counterpart h8, so a 3-D-only part is
    checked on the same geometry as every other.
    """
    if dims is None or 2 in dims:
        return run
    method = run.solver.method.replace("q4+", "h8+") if run.solver.method.startswith("q4+") else run.solver.method
    return run.updated(Lz=2.0 / run.solver.m, method=method)


def model_name(run):
    """Toporia's own model for the run's dimension: q4 in 2-D, h8 in 3-D."""
    return "h8" if run.scenario.Lz > 0 else "q4"


def iterate(method, iterations, tol=0.0):
    """Step as the engine does, with its stopping rule (design change below tol, or the method's own)."""
    for iteration in range(1, iterations + 1):
        method.step(iteration)
        if method.get_change() < tol or method.is_converged():
            break


def gradient_check(value, gradient, x, movable, report, name, count=6, h=1e-5, rtol=1e-3):
    """Compare `gradient` with central differences of `value` at the largest movable entries."""
    with report.step(name) as check:
        gradient = np.asarray(gradient, dtype=float)
        assert gradient.shape == np.shape(x), f"gradient has shape {gradient.shape}, design {np.shape(x)}"
        assert np.all(np.isfinite(gradient)), "gradient has non-finite entries"
        candidates = np.flatnonzero(np.asarray(movable).reshape(-1))
        if candidates.size == 0:
            raise Skip("no movable variables")
        order = candidates[np.argsort(-np.abs(gradient.reshape(-1)[candidates]))][:count]
        scale = max(float(np.max(np.abs(gradient))), 1e-300)
        worst, where = 0.0, None
        for index in order:
            plus, minus = np.array(x, dtype=float), np.array(x, dtype=float)
            plus.reshape(-1)[index] += h
            minus.reshape(-1)[index] -= h
            fd = (value(plus) - value(minus)) / (2 * h)
            exact = gradient.reshape(-1)[index]
            error = abs(fd - exact) / max(abs(fd), abs(exact), 1e-6 * scale)
            if error > worst:
                worst, where = error, (int(index), exact, fd)
        assert worst <= rtol, (f"off by {worst:.2%} at flat index {where[0]}: "
                               f"gradient {where[1]:.6g}, finite difference {where[2]:.6g}")
        check.detail = f"largest relative error {worst:.1e} over {len(order)} entries"


def random_design(model, seed=0):
    """The model's start design, perturbed and kept inside its bounds (and away from 0 and 1)."""
    lower, upper = model.bounds()
    rng = np.random.default_rng(seed)
    x = np.asarray(model.initial_design(), dtype=float) + rng.uniform(-0.15, 0.15, np.shape(lower))
    return np.clip(x, np.maximum(lower, 0.05), np.maximum(np.minimum(upper, 0.95), lower))


def optimiser_threads():
    """Every running background optimiser thread (they are all named toporia-...)."""
    return {t for t in threading.enumerate() if t.name.startswith("toporia-")}


def no_threads_left(report, before):
    """Fail if the plugin left an optimiser thread running; threads from before the check don't count."""
    with report.step("no background thread left running"):
        alive = sorted(t.name for t in optimiser_threads() - before)
        assert not alive, f"still running: {alive}"
