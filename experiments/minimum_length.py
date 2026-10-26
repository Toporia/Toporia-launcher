"""Reproducible feasible-seed validation, not a general minimum-length solver.

Run: python -m experiments.minimum_length
The unchanged identity density representation is seeded explicitly in this
research script; it does not add a file warm-start feature to the GUI.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from toporia.engine.loop import initialized_method
from toporia.framework import PointLoad
from toporia.plugins.problems import get_run


def seeded_validation():
    """Optimise a resolved straight cantilever under both geometric constraints.

    Linear ersatz interpolation deliberately keeps a material derivative in
    the nearly empty background. This is not a penalised SIMP benchmark.
    """
    run = get_run("Cantilever").updated(
        Lx=24, Ly=16, point_loads=[PointLoad(x=24, y=8)], m=1, volfrac=0.5,
        method="q4+nlopt_mma", filter_specs=[], interpolation={"type": "simp", "penal": 1},
        constraints=[{"type": "minimum_length", "phase": phase, "min_length": 4}
                     for phase in ("solid", "void")],
        **{"method.nlopt_maxeval": 500, "method.nlopt_report_step": 1e-4, "tol": 0})
    method = initialized_method(run)
    try:
        # The representation is the identity: these are also the physical densities.
        initial = np.full(method.x.shape, 0.002)
        initial[4:12, :] = 0.998
        method.x = initial.copy()
        first = method._model.evaluate(method.x, gradients=False)
        for iteration in range(1, 501):
            method.step(iteration)
            if method.is_converged():
                break
        # Recompute at the actual new design, rather than its preceding iterate.
        final = method._model.evaluate(method.x, gradients=False)
        density = method.get_density().copy()
        residuals = [float(c.value) for c in final.constraints]
        report = {
            "initial_compliance": float(first.objective), "compliance": float(final.objective),
            "volume_fraction": float(density.mean()), "solid_void_residuals": residuals,
            "iterations": iteration, "solves": method.solves,
            "optimizer": method.report(),
            "feasible": bool(density.mean() <= 0.5+1e-8 and max(residuals) <= 1e-6),
            "limitations": "24x16 cells; 4 mm proxy target; linear ersatz; explicit feasible seed; no global-optimum or exact-width certificate",
        }
        return initial, density, report
    finally:
        method.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results/minimum-length-validation"))
    args = parser.parse_args()
    initial, density, report = seeded_validation()
    args.out.mkdir(parents=True, exist_ok=True)
    np.save(args.out/"initial.npy", initial)
    np.save(args.out/"density.npy", density)
    (args.out/"report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for axis, rho, title in zip(axes, (initial, density), ("Feasible straight-bar seed", "Optimised physical density"), strict=True):
        axis.imshow(rho, cmap="gray_r", origin="lower", vmin=0, vmax=1, extent=(0, 24, 0, 16))
        axis.set(xlabel="x (mm)", ylabel="y (mm)", title=title)
    figure.suptitle(f"Minimum-length proxy: solid + void, 4 mm; C {report['initial_compliance']:.3f} → {report['compliance']:.3f}\n"
                   f"V={report['volume_fraction']:.6f}; residuals={report['solid_void_residuals']}; linear ersatz")
    figure.savefig(args.out/"validation.png", dpi=160)
    plt.close(figure)
    print(json.dumps(report, indent=2))
    if not report["feasible"]:
        raise SystemExit("Final geometric proxy constraints or volume budget are violated")


if __name__ == "__main__":
    main()
