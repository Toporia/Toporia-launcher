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


def validate(preset, iterations=600, mesh=.5, updater="adam", seed=0, beta=0, refine=2, settle_move=0):
    params = {"lr": .01, "lr_decay": .995} if updater == "adam" else {"move": .005}
    filters = [{"type": "density", "rmin": 1.5}]
    if beta:
        filters.append({"type": "heaviside", "beta": beta, "beta_max": beta})
        if updater == "mma":
            params.update(asyinit=0.5/(2*beta+1), asyincr=1.05, asydecr=0.65)
    run = get_run(preset).updated(method=f"q4+{updater}", method_params=params, m=mesh,
                                  max_iter=iterations, tol=0., save_every=0,
                                  representation={"type": "neural", "width": 20, "depth": 2, "seed": seed},
                                  filter_specs=filters)
    method = initialized_method(run)
    initial = method._model.evaluate(method.x, gradients=False).objective
    for iteration in range(1, iterations + 1):
        if settle_move and iteration > iterations*0.6:
            method.set_parameter("method.move", settle_move)
        previous = method.get_density().copy()
        previous_weights = method.x.copy()
        method.step(iteration)
        physical_change = float(np.max(np.abs(method.get_density()-previous)))
        weight_change = float(np.max(np.abs(method.x-previous_weights)))
    final = method._model.evaluate(method.x, gradients=False)
    rho = method.get_density()
    allowed = int(np.floor(run.scenario.volfrac*rho.size))
    cutoff = max(0.5, float(np.sort(rho.ravel())[-allowed-1]))
    solid = rho > cutoff
    state = method._model.engine.solve(solid.astype(float))
    binary_compliance = method._model.objective.evaluate(state, gradient=False).value
    report = {"preset": preset, "updater": updater, "seed": seed, "projection_beta": beta,
            "iterations": iterations, "shape": rho.shape,
            "variables": method.x.size, "initial_compliance": initial, "final_compliance": final.objective,
            "volume_fraction": float(rho.mean()), "volume_limit": run.scenario.volfrac,
            "gray_fraction_0.1_0.9": float(np.mean((rho > .1) & (rho < .9))),
            "last_weight_change": weight_change, "last_physical_change": physical_change,
            "reported_change": method.get_change(), "settle_move": settle_move,
            "budget_thresholded": {"cutoff": cutoff, "volume_fraction": float(solid.mean()),
                                   "compliance": float(binary_compliance)}}
    if refine > 1:
        # The same learned network is sampled on a finer grid without training.
        # rmin is measured in cells: scale it to preserve the physical radius.
        fine_filters = [{**spec, **({"rmin": spec["rmin"]*refine} if "rmin" in spec else {})}
                        for spec in filters]
        finer = initialized_method(run.updated(m=mesh*refine, filter_specs=fine_filters))
        try:
            fine = finer._model.evaluate(method.x, gradients=False)
            fine_rho = finer._model.physical(method.x)
            report["finer_mesh"] = {"shape": fine_rho.shape, "compliance": float(fine.objective),
                                    "volume_fraction": float(fine_rho.mean()),
                                    "gray_fraction_0.1_0.9": float(np.mean((fine_rho > .1) & (fine_rho < .9)))}
        finally:
            finer.close()
    method.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--mesh", type=float, default=.5)
    parser.add_argument("--updater", choices=("adam", "mma"), default="adam")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--beta", type=int, choices=(0, 8, 16), default=0,
                        help="Optional fixed Heaviside sharpness; 0 omits projection")
    parser.add_argument("--refine", type=int, choices=(1, 2), default=2)
    parser.add_argument("--settle-move", type=float, default=0,
                        help="Optional MMA weight move for the final 40 percent of iterations")
    args = parser.parse_args()
    if args.iterations < 1 or not np.isfinite(args.mesh) or args.mesh <= 0:
        parser.error("Use positive iterations and a finite positive mesh resolution")
    if not 0 <= args.seed <= 1000000:
        parser.error("Use a seed from 0 to 1000000")
    if args.settle_move and (args.updater != "mma" or not np.isfinite(args.settle_move)
                            or not 1e-5 <= args.settle_move <= .005):
        parser.error("--settle-move needs MMA and a finite weight move in [0.00001, 0.005]")
    print(json.dumps([validate(preset, args.iterations, args.mesh, args.updater,
                               args.seed, args.beta, args.refine, args.settle_move)
                      for preset in ("MBB Beam", "Cantilever")], indent=2))


if __name__ == "__main__":
    main()
