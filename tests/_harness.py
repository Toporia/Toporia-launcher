"""_harness.py — shared run helper for the regression suite.

Keeps the "run a config and collect what we assert on" logic in one place so
test_golden.py and regenerate_baselines.py can never diverge.
"""

from dataclasses import replace

import numpy as np

from toporia.core.contract import OBJECTIVE
from toporia.core.problem import RectangularProblem
from toporia.library.methods import make_method

# Everything the golden test compares.  Deliberately small: the density field
# is the universal output of every method, and the objective plus iteration
# count catch changes in the solver and the convergence policy respectively.
FIELDS = ("density", "objective", "iterations")


def run_case(cfg, output_dir):
    """Run one optimisation to completion and return the asserted quantities.

    Mirrors engine.runner.run_single's loop exactly, but without ResultStore, so
    the baselines do not depend on file output.  The stopping rule lives in the
    engine now, so it is reproduced here rather than asked of the method.
    """
    cfg = replace(cfg, output_dir=output_dir)
    method = make_method(cfg.method)
    method.initialize(RectangularProblem(cfg), cfg)

    iteration = 0
    for iteration in range(1, cfg.max_iter + 1):
        method.step(iteration)
        if method.get_change() < cfg.tol or method.is_converged():
            break
    return {
        "density":    np.asarray(method.get_density(), dtype=float),
        "objective":  np.array(float(method.get_responses()[OBJECTIVE])),
        "iterations": np.array(int(iteration)),
    }
