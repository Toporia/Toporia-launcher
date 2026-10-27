"""Bounded fixed-beta projection benchmarks; no output files or installations.

Run: python -m experiments.fixed_projection --iterations 600 --mesh 1
Uses the fixed-projection preset's independent MMA recipe on two benchmarks.
"""

import argparse
import json

import numpy as np

from toporia.engine.loop import initialized_method
from toporia.plugins.problems import get_run


def validate(preset, iterations=600, mesh=1.0):
    recipe = get_run("MBB Beam (Fixed Projection)").solver
    run = get_run(preset).updated(
        method=recipe.method, method_params=recipe.method_params,
        filter_specs=recipe.filter_specs, schedules=[], variants={},
        m=mesh, max_iter=iterations, tol=0.0, save_every=0,
    )
    method = initialized_method(run)
    initial = method._model.evaluate(method.x, gradients=False).objective
    for iteration in range(1, iterations + 1):
        method.step(iteration)
    final = method._model.evaluate(method.x, gradients=False)
    rho = method.get_density()
    return {"preset": preset, "iterations": iterations, "shape": rho.shape,
            "beta": 16, "initial_compliance": initial, "final_compliance": final.objective,
            "volume_fraction": final.volume / rho.size, "volume_limit": run.scenario.volfrac,
            "gray_fraction_0.1_0.9": float(np.mean((rho > 0.1) & (rho < 0.9))),
            "gray_indicator": float(np.mean(4 * rho * (1 - rho))),
            "last_change": method.get_change()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--mesh", type=float, default=1.0)
    args = parser.parse_args()
    if args.iterations < 1 or not np.isfinite(args.mesh) or args.mesh <= 0:
        parser.error("Use positive iterations and a finite positive mesh resolution")
    print(json.dumps([validate(p, args.iterations, args.mesh)
                      for p in ("MBB Beam", "Cantilever")], indent=2))


if __name__ == "__main__":
    main()
