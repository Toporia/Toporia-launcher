# checks/postprocess.py — is a post-processor sound?
#
# Run on a small finished design, it returns plain metrics (numbers, booleans
# or None), writes only into its folder and every file it names is there and
# not empty, does not change the design it was given, and gives the same
# numbers when run again.

import math
import tempfile
from pathlib import Path

import numpy as np

from toporia.framework.params import resolve_params
from toporia.framework.problem.mesh import RectangularProblem

from .common import check_declaration, iterate, small_run
from .report import Report


def _finished_design():
    """A short q4+oc run on the benchmark problem: (run, problem, density)."""
    from toporia.engine.loop import initialized_method
    run = small_run(method="q4+oc", m=0.4, max_iter=8, tol=0.0)
    method = initialized_method(run)
    iterate(method, 8)
    return run, RectangularProblem(run.scenario, run.solver.m), method.get_density()


def check_postprocessor(cls):
    """Check a PostProcessor: plain metrics, its files, the design untouched, the same numbers twice."""
    from toporia.framework.parts.postprocess import Result
    report = Report(f"post-processor {cls.__name__} ({getattr(cls, 'name', '?')})")
    check_declaration(report, cls)
    if not report.ok:
        return report
    run, problem, density = _finished_design()

    with tempfile.TemporaryDirectory() as folder:
        def once(sub):
            result = Result(density=density.copy(), problem=problem, run=run, folder=Path(folder) / sub)
            metrics = cls(**resolve_params(cls.name, cls.params, {})).process(result)
            return result, metrics

        with report.step("plain metrics, and the files it names") as check:
            result, metrics = once("a")
            assert isinstance(metrics, dict), f"process() returned {type(metrics).__name__}, not a dict"
            for name, value in metrics.items():
                plain = value is None or isinstance(value, (bool, int, float, np.integer, np.floating, np.bool_))
                assert plain, f"metric {name!r} is a {type(value).__name__}; return numbers, booleans or None"
                if isinstance(value, (float, np.floating)):
                    assert math.isfinite(value), f"metric {name!r} is {value}"
            for path in result.files:
                assert path.exists() and path.stat().st_size > 0, f"{path.name} was named but is missing or empty"
                assert Path(folder) / "a" in path.parents, f"{path} is outside the post-processing folder"
            assert np.array_equal(result.density, density), "it changed the design it was given"
            check.detail = f"{len(metrics)} metric(s), {len(result.files)} file(s)"
        if not report.ok:
            return report

        with report.step("the same numbers when run again"):
            _, again = once("b")
            assert again == metrics, f"first {metrics}, then {again}"
    return report
