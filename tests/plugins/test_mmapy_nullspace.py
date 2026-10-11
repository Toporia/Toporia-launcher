"""test_mmapy_nullspace.py — the GPL-3 optimisers wrapped as optional updaters.

mmapy (Svanberg's MMA and GCMMA, ported by Arjen Deetman) and nullspace_optimizer
(Feppon's null-space method) are GPL-3, so Toporia (Apache-2.0) never bundles or
requires them.  These tests skip when they are not installed, and one test checks
that the updaters then explain how to install them rather than failing obscurely.

The cross-check that matters: mmapy_mma is a line-by-line port of Svanberg's
reference code, so it and Toporia's own `mma` (a different subproblem solver)
should land on the same MBB design.
"""

import importlib.util
import subprocess
import sys

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.framework.parts.method import OBJECTIVE
from toporia.plugins.problems import get_run
from toporia.plugins.updaters import UPDATERS

HAVE_MMAPY = importlib.util.find_spec("mmapy") is not None
HAVE_NULLSPACE = importlib.util.find_spec("nullspace_optimizer") is not None


def _optimise(updater, iterations=60, problem="MBB Beam", **values):
    """Run q4+updater for a fixed number of iterations; return the finished method."""
    values.setdefault("m", 0.4)
    run = get_run(problem).updated(method=f"q4+{updater}", max_iter=iterations, tol=0.0, **values)
    method = initialized_method(run)
    try:
        for iteration in range(1, iterations + 1):
            method.step(iteration)
            if method.is_converged():
                break
    finally:
        method.close()
    return method


def _compliance(method):
    return float(method._model.evaluate(method.x, gradients=False).objective)


# ── Always run: registration and the licence-driven optional-dependency contract ──────────

@pytest.mark.parametrize("name, package", [("mmapy_mma", "mmapy"), ("mmapy_gcmma", "mmapy"),
                                           ("nullspace", "nullspace_optimizer")])
def test_declared_as_optional_dependencies(name, package):
    cls = UPDATERS.get(name)
    assert cls.dependencies == (package,)


def test_importing_the_adapters_does_not_import_the_gpl_libraries():
    """Registered and importable without the libraries: they are loaded only when a run starts."""
    script = (
        "import sys\n"
        "import toporia.plugins.updaters.mmapy_optimizers, toporia.plugins.updaters.nullspace\n"
        "print('mmapy' in sys.modules, 'nullspace_optimizer' in sys.modules)\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert result.stdout.split()[-2:] == ["False", "False"]


@pytest.mark.parametrize("module, function, package", [
    ("mmapy_optimizers", "import_mmapy", "mmapy"),
    ("nullspace", "import_nullspace", "nullspace_optimizer"),
])
def test_the_install_hint_appears_when_the_library_is_missing(module, function, package):
    script = (
        f"import sys; sys.modules[{package!r}] = None   # make it unimportable\n"
        f"from toporia.plugins.updaters.{module} import {function}\n"
        "try:\n"
        f"    {function}()\n"
        "except ImportError as error:\n"
        "    print(error)\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert "GPL-3" in result.stdout and "pip install" in result.stdout


# ── mmapy ──────────────────────────────────────────────────────────────────

requires_mmapy = pytest.mark.skipif(not HAVE_MMAPY, reason="optional dependency: pip install mmapy (GPL-3)")
requires_nullspace = pytest.mark.skipif(not HAVE_NULLSPACE,
                                        reason="optional dependency: pip install nullspace_optimizer (GPL-3)")


@requires_mmapy
def test_mmapy_mma_agrees_with_our_mma():
    """Svanberg's reference port and our bisection MMA reach the same MBB compliance."""
    ours = _compliance(_optimise("mma"))
    theirs = _compliance(_optimise("mmapy_mma"))
    assert theirs == pytest.approx(ours, rel=0.02), f"mma={ours:.4f} mmapy_mma={theirs:.4f}"


@requires_mmapy
def test_mmapy_gcmma_agrees_and_its_inner_iterations_are_counted():
    ours = _compliance(_optimise("mma"))
    method = _optimise("mmapy_gcmma")
    assert _compliance(method) == pytest.approx(ours, rel=0.02)
    report = method.report()
    assert report["outer_iterations"] > 0 and report["inner_iterations"] >= 0
    # Every inner iteration is one more evaluation of the model, and it must show in the count.
    assert method.get_responses()["solves"] >= report["outer_iterations"] + report["inner_iterations"]


@requires_mmapy
def test_mmapy_respects_the_bounds_on_a_problem_with_holes():
    method = _optimise("mmapy_gcmma", iterations=4, problem="Drone Arm", m=0.3, volfrac=0.4)
    problem = method.problem
    density = method.get_density()
    assert np.all(density[problem.void_elements] < 1e-6)
    assert np.all(density[problem.passive_elements] > 1.0 - 1e-6)


# ── nullspace ──────────────────────────────────────────────────────────────

@requires_nullspace
def test_nullspace_reaches_the_mma_compliance_within_the_budget():
    reference = _compliance(_optimise("mma"))
    method = _optimise("nullspace", iterations=100)
    assert _compliance(method) <= 1.05 * reference
    assert method.get_density().mean() <= get_run("MBB Beam").scenario.volfrac * 1.01
    assert method.get_responses()[OBJECTIVE] > 0


@requires_nullspace
def test_nullspace_respects_the_bounds_on_a_problem_with_holes():
    method = _optimise("nullspace", iterations=4, problem="Drone Arm", m=0.3, volfrac=0.4)
    problem = method.problem
    density = method.get_density()
    assert np.all(density[problem.void_elements] < 1e-6)
    assert np.all(density[problem.passive_elements] > 1.0 - 1e-6)


@requires_nullspace
def test_nullspace_leaves_no_thread_behind():
    import threading
    before = {t.name for t in threading.enumerate()}
    _optimise("nullspace", iterations=3)
    assert not [t for t in threading.enumerate() if t.name.startswith("toporia-") and t.name not in before]
