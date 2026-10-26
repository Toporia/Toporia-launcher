"""Matched fine/coarse-analysis benchmarks with fresh fine-Q4 verification.

Run: python -m experiments.multiresolution --iterations 100 --mesh 1 --radius 3
The design/density grid, material law, loads, filter and OC steps stay fixed;
only the displacement space changes. Timings are illustrative single runs.
No output files are written. A fine verification is essential: a coarse space
can assign a high stiffness to disconnected fine features.
"""

import argparse
import json
from time import perf_counter

import numpy as np

from toporia.engine.loop import initialized_method
from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
from toporia.plugins.problems import get_run


def validate(preset, factor=2, iterations=100, mesh=1.0, radius=3.0):
    run = get_run(preset).updated(
        method="q4_multiresolution+oc", method_params={"coarsening": factor},
        m=mesh, max_iter=iterations, tol=0.0, save_every=0,
        filter_specs=[{"type": "density", "rmin": radius}],
    )
    method = initialized_method(run)
    model = method._model
    initial = model.evaluate(method.x, gradients=False).objective
    timer = perf_counter()
    for iteration in range(1, iterations + 1):
        method.step(iteration)
    final = model.evaluate(method.x, gradients=False)
    optimisation_seconds = perf_counter() - timer
    density = method.get_density()
    resolved = Q4PlaneStress()
    resolved.initialize(model.problem, {}, model.engine.material)
    timer = perf_counter()
    state = resolved.solve(density)
    fine_compliance = sum(w * c for w, c in zip(state.weights, state.compliances, strict=True))
    return {
        "preset": preset, "density_shape": density.shape,
        "analysis_shape": model.engine.analysis_shape, "coarsening": factor,
        "iterations": iterations, "radius_in_fine_cells": radius,
        "linear_system_dofs": model.engine.system_dofs,
        "initial_analysis_compliance": initial, "final_analysis_compliance": final.objective,
        "fine_verified_compliance": fine_compliance,
        "relative_compliance_underestimate": float(1 - final.objective / fine_compliance),
        "physical_volume_fraction": float(density.mean()), "volume_limit": run.scenario.volfrac,
        "last_change": method.get_change(), "optimisation_seconds": optimisation_seconds,
        "fine_verification_seconds": perf_counter() - timer,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--mesh", type=float, default=1.0)
    parser.add_argument("--radius", type=float, default=3.0)
    args = parser.parse_args()
    if args.iterations < 1 or not np.isfinite(args.mesh) or args.mesh <= 0:
        parser.error("Use positive iterations and a finite positive mesh resolution")
    print(json.dumps([validate(preset, factor, args.iterations, args.mesh, args.radius)
                      for preset in ("MBB Beam", "Cantilever") for factor in (1, 2)], indent=2))


if __name__ == "__main__":
    main()
