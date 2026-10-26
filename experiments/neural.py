"""Bounded NumPy coordinate-network optimisation, with fresh final responses.

Run: python -m experiments.neural --iterations 600 --mesh 0.5 --updater adam
No output files are written. This is a smooth TOuNN-style variant, not the
reference PyTorch/AMSGrad training procedure. Seed/capacity can change results.
"""

import argparse
import json

import numpy as np

from toporia.engine.loop import initialized_method
from toporia.plugins.problems import get_run


def validate(preset, iterations=600, mesh=.5, updater="adam"):
    params = {"lr": .01, "lr_decay": .995} if updater == "adam" else {"move": .005}
    run = get_run(preset).updated(method=f"q4+{updater}", method_params=params, m=mesh,
                                  max_iter=iterations, tol=0., save_every=0,
                                  representation={"type": "neural", "width": 20, "depth": 2, "seed": 0},
                                  filter_specs=[{"type": "density", "rmin": 1.5}])
    method = initialized_method(run)
    initial = method._model.evaluate(method.x, gradients=False).objective
    for iteration in range(1, iterations + 1):
        method.step(iteration)
    final = method._model.evaluate(method.x, gradients=False)
    rho = method.get_density()
    return {"preset": preset, "updater": updater, "iterations": iterations, "shape": rho.shape,
            "variables": method.x.size, "initial_compliance": initial, "final_compliance": final.objective,
            "volume_fraction": float(rho.mean()), "volume_limit": run.scenario.volfrac,
            "gray_fraction_0.1_0.9": float(np.mean((rho > .1) & (rho < .9))),
            "last_weight_change": method.get_change()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--mesh", type=float, default=.5)
    parser.add_argument("--updater", choices=("adam", "mma"), default="adam")
    args = parser.parse_args()
    if args.iterations < 1 or not np.isfinite(args.mesh) or args.mesh <= 0:
        parser.error("Use positive iterations and a finite positive mesh resolution")
    print(json.dumps([validate(preset, args.iterations, args.mesh, args.updater)
                      for preset in ("MBB Beam", "Cantilever")], indent=2))


if __name__ == "__main__":
    main()
