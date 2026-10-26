"""Reproducible machining-filter validation; prints JSON without writing runs.

Run ``python -m experiments.machining --iterations 80``. These coarse tests
validate integration and improvement, not reproduction of the paper's fine
meshes or a certificate for a finite milling tool. The ray check is performed
independently on the thresholded final physical density.
"""

import argparse
import json

import numpy as np

from toporia.engine.loop import initialized_method
from toporia.plugins.problems import get_run


def validate(preset, iterations=80):
    """Small-move MMA from a calibrated uniform source with a top-side tool."""
    method_name = "h8+mma" if preset == "Cantilever 3D" else "q4+mma"
    run = get_run(preset).updated(
        method=method_name, m=0.4, tol=0.0, max_iter=iterations, save_every=0,
        method_params={"move": 0.01, "asyinit": 0.03, "asyincr": 1.05, "asydecr": 0.65},
        filter_specs=[{"type": "density", "rmin": 1.5}, {"type": "machining"}],
    )
    method = initialized_method(run)
    model = method._model
    initial = model.evaluate(method.x, gradients=False).objective
    for iteration in range(1, iterations + 1):
        method.step(iteration)
    final = model.evaluate(method.x, gradients=False)
    density = method.get_density()
    solid = density >= 0.5
    # A top-side tool travels down each y-ray. A void after the first solid is
    # inaccessible; this discrete test does not use the PDE or its projection.
    rays = np.moveaxis(solid, -2, 0)[::-1]
    blocked = np.maximum.accumulate(rays, axis=0)
    return {
        "preset": preset, "shape": density.shape, "iterations": iterations,
        "initial_compliance": initial, "final_compliance": final.objective,
        "physical_volume_fraction": float(density.mean()), "volume_limit": run.scenario.volfrac,
        "last_change": method.get_change(),
        "inaccessible_thresholded_void_cells": int(np.sum(blocked & ~rays)),
        "gray_fraction_0.1_to_0.9": float(np.mean((density > 0.1) & (density < 0.9))),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=80)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    print(json.dumps([validate(p, args.iterations) for p in ("MBB Beam", "Cantilever 3D")], indent=2))


if __name__ == "__main__":
    main()
