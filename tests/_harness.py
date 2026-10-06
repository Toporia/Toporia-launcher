"""_harness.py — shared run helper for the regression suite.

Keeps the "run a Run and collect what we assert on" logic in one place so
test_golden.py and regenerate_baselines.py can never diverge.
"""

import numpy as np

from toporia.engine.loop import initialized_method
from toporia.framework.parts.method import OBJECTIVE

# Everything the golden test compares.  Deliberately small: the density field
# is the universal output of every method, and the objective plus iteration
# count catch changes in the solver and the convergence policy respectively.
FIELDS = ("density", "objective", "iterations")


def run_case(run, output_dir):
    """Run one optimisation to completion and return the asserted quantities.

    Mirrors engine.runner.run_single's loop exactly, but without ResultStore, so
    the baselines do not depend on file output.  The problem and the method are
    built by the engine's own initialized_method, so the wiring under test is
    the real one.
    """
    run = run.with_output_dir(output_dir)
    method = initialized_method(run)

    iteration = 0
    for iteration in range(1, run.solver.max_iter + 1):
        method.step(iteration)
        if method.get_change() < run.solver.tol or method.is_converged():
            break
    return {
        "density":    np.asarray(method.get_density(), dtype=float),
        "objective":  np.array(float(method.get_responses()[OBJECTIVE])),
        "iterations": np.array(int(iteration)),
    }
