"""test_pymoto_backend.py — the contract canary.

pyMOTO knows nothing about Toporia.  If the adapter in
library/methods/pymoto_compliance.py can drive it using only core.contract and
core.problem, then those two modules contain no Toporia-specific assumptions.

A failure here after a contract change is the signal that the contract has
quietly grown a dependency on how Toporia's own methods happen to work.
"""

from dataclasses import replace

import numpy as np
import pytest

from toporia.core.contract import OBJECTIVE
from toporia.core.problem import RectangularProblem
from toporia.library.methods import make_method
from toporia.library.problems import get_config

pymoto = pytest.importorskip("pymoto", reason="optional dependency: pip install pymoto")


def _run(method_name, problem_name="MBB Beam", iterations=25, **overrides):
    overrides.setdefault("m", 0.5)
    cfg = replace(get_config(problem_name), max_iter=iterations, tol=0.0, **overrides)
    method = make_method(method_name)
    method.initialize(RectangularProblem(cfg), cfg)
    for iteration in range(1, cfg.max_iter + 1):
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
