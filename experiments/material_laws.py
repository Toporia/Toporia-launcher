"""Bounded material-law benchmarks, reporting geometric and effective volume.

Run: python -m experiments.material_laws --iterations 300 --mesh 1
No files are written. Final responses are recomputed on the final density.
"""

import argparse
import json

import numpy as np

from toporia.engine.loop import initialized_method
from toporia.plugins.problems import get_run


def validate(preset, iterations=300, mesh=1.):
    run = get_run(preset).updated(method="q4+mma", method_params={"move": .05}, m=mesh,
                                  max_iter=iterations, tol=0., save_every=0,
                                  interpolation={"type": "sinh", "penal": 3.},
                                  filter_specs=[{"type": "density", "rmin": 1.5}])
    method = initialized_method(run)
    initial = method._model.evaluate(method.x, gradients=False).objective
    for iteration in range(1, iterations+1):
        method.step(iteration)
    final = method._model.evaluate(method.x, gradients=False)
    rho = method.get_density()
    return {"preset": preset, "law": "sinh", "iterations": iterations, "shape": rho.shape,
            "initial_compliance": initial, "final_compliance": final.objective,
            "geometric_volume_fraction": float(rho.mean()), "effective_volume_fraction": final.volume/rho.size,
            "volume_limit": run.scenario.volfrac,
            "gray_fraction_0.1_0.9": float(np.mean((rho > .1) & (rho < .9))),
            "last_change": method.get_change()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--mesh", type=float, default=1.)
    args = parser.parse_args()
    if args.iterations < 1 or not np.isfinite(args.mesh) or args.mesh <= 0:
        parser.error("Use positive iterations and a finite positive mesh resolution")
    print(json.dumps([validate(preset, args.iterations, args.mesh)
                      for preset in ("MBB Beam", "Cantilever")], indent=2))


if __name__ == "__main__":
    main()
