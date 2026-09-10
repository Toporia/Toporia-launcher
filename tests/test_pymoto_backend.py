"""test_pymoto_backend.py — the contract canary.

pyMOTO knows nothing about Toporia.  If the model in
library/models/pymoto_compliance.py can drive it using only core.contract and
core.problem, then those two modules contain no Toporia-specific assumptions.

A failure here after a contract change is the signal that the contract has
quietly grown a dependency on how Toporia's own methods happen to work.
"""

import importlib.util
import subprocess
import sys

import numpy as np
import pytest

from toporia.core.contract import OBJECTIVE
from toporia.engine.runner import initialized_method
from toporia.library.problems import get_run

# Checked without importing pyMOTO: importing it switches matplotlib's backend,
# and the library only ever imports it through import_pymoto(), which undoes that.
pytestmark = pytest.mark.skipif(importlib.util.find_spec("pymoto") is None,
                                reason="optional dependency: pip install pymoto")


def _run(method_name, problem_name="MBB Beam", iterations=25, **overrides):
    overrides.setdefault("m", 0.5)
    run = get_run(problem_name).updated(method=method_name, max_iter=iterations, tol=0.0, **overrides)
    method = initialized_method(run)
    for iteration in range(1, run.solver.max_iter + 1):
        method.step(iteration)
    return method


def test_satisfies_the_contract():
    """Every abstract member must work, with the shapes and types promised."""
    method = _run("pymoto", iterations=5)
    density = method.get_density()
    assert density.shape == (10, 30)
    assert np.all(np.isfinite(density))
    assert density.min() >= -1e-9 and density.max() <= 1 + 1e-9
    assert OBJECTIVE in method.get_responses()
    assert np.isfinite(method.get_change())
    assert method.is_converged() is False   # default hook, not overridden


def test_agrees_with_the_native_solver():
    """Different FE code, different DOF numbering, same physics.

    Both minimise compliance on the MBB benchmark to the same volume fraction,
    so the compliances must land close even though nothing is shared between them.
    """
    native = _run("density_mma")
    foreign = _run("pymoto")

    c_native = native.get_responses()[OBJECTIVE]
    c_foreign = foreign.get_responses()[OBJECTIVE]
    assert c_foreign == pytest.approx(c_native, rel=0.10), (
        f"native={c_native:.4f} pymoto={c_foreign:.4f}"
    )
    assert foreign.get_density().mean() == pytest.approx(native.get_density().mean(), abs=0.02)


def test_honours_passive_and_void_bounds():
    """The bounds from problem.lower_bound / upper_bound must be respected exactly.

    The drone arm has both forced-solid rings and forced-void holes, so this
    checks that the mask-to-bounds translation survives the trip through pyMOTO.
    """
    method = _run("pymoto", problem_name="Drone Arm", iterations=4, m=0.3, volfrac=0.4)
    problem = method.problem
    density = method.get_density()
    assert np.all(density[problem.void_elements] < 1e-6)
    assert np.all(density[problem.passive_elements] > 1.0 - 1e-6)


def test_importing_pymoto_leaves_the_matplotlib_backend_alone():
    """pyMOTO calls matplotlib.use("TkAgg") on import; import_pymoto() must undo it.

    Otherwise selecting a pyMOTO method would switch every figure the GUI or the
    CLI saves to Tk.  Run in a fresh interpreter, because in this process pyMOTO
    may already have been imported by an earlier test.
    """
    script = (
        "import matplotlib; matplotlib.use('Agg')\n"
        "from toporia.library.models.pymoto_compliance import import_pymoto\n"
        "import_pymoto()\n"
        "print(matplotlib.get_backend())\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert result.stdout.strip().lower() == "agg"
