"""Bounded Gaynor–Guest cell-projection benchmarks; prints measurements, saves no runs.

Run: python -m experiments.self_support --iterations 1000
These use Toporia's own cell-centred discretisation, not the paper's nodal code.
The independent geometric check tests the thresholded physical field against a
one-layer 45-degree support stencil; it is stricter than the multi-layer wedge
in some places and is a diagnostic, not a printing-process simulation.
"""

import argparse
import json

import numpy as np

from toporia.engine.loop import initialized_method, make_schedules
from toporia.plugins.problems import get_run


def binary_diagnostic(density, model, threshold):
    """Re-solve a thresholded field and independently check its one-layer supports.

    Strict > makes equal-valued cutoff cells void, so a quantile cutoff never
    exceeds the selected cell-count budget. Thresholding may remove supports.
    """
    solid = density > threshold
    state = model.engine.solve(solid.astype(float))
    compliance = model.objective.evaluate(state, gradient=False).value
    below = np.pad(solid[:-1], ((0, 0), (1, 1)), constant_values=False)
    supported = below[:, :-2] | below[:, 1:-1] | below[:, 2:]
    return {"threshold": float(threshold), "volume_fraction": float(solid.mean()),
            "compliance": float(compliance),
            "unsupported_cells_one_layer_45_degree": int(np.sum(solid[1:] & ~supported))}


def validate(preset, iterations=1000, mesh=1.0, updater="mma"):
    settings = {"move": 0.01}
    if updater == "mma":
        settings.update(asyinit=0.02, asyincr=1.05, asydecr=0.65)
    run = get_run(preset).updated(
        method=f"q4+{updater}", m=mesh, tol=0.0, max_iter=iterations, save_every=0,
        interpolation={"type": "ramp", "q": 10},
        method_params=settings,
        filter_specs=[{"type": "self_support", "beta_local": 10}],
        schedules=[{"path": "interpolation.q", "type": "steps", "start": 10,
                    "end": 30, "step": 10, "every": 200},
                   {"path": "filters[0].beta_local", "type": "steps", "start": 10,
                    "end": 25, "step": 15, "every": 50},
                   {"path": "method.move", "type": "steps", "start": 0.01,
                    "end": 0.0005, "step": 0.0095, "every": 400}],
    )
    if updater != "mma":
        # pyMOTO's wrapper fixes its move limit at setup; its GCMMA inner
        # conservative checks control the accepted step instead.
        run = run.updated(schedules=run.solver.schedules[:2])
    method = initialized_method(run)
    model = method._model
    schedules = make_schedules(run)
    # Compare the initial and final physical densities with the same final
    # material law, rather than mixing compliances at different RAMP penalties.
    final_q = schedules[0][1].value(iterations - 1)
    method.set_parameter("interpolation.q", final_q)
    initial = model.evaluate(method.x, gradients=False).objective
    for iteration in range(1, iterations + 1):
        for path, schedule in schedules:
            method.set_parameter(path, schedule.value(iteration - 1))
        method.step(iteration)
        if iteration % 100 == 0:
            print(f"{preset}, {updater}: {iteration}/{iterations}, physical/design change "
                  f"{method.get_change():.4g}", flush=True)
    final = model.evaluate(method.x, gradients=False)
    density = method.get_density()
    binary = binary_diagnostic(density, model, 0.5)
    # Retain at most floor(volfrac * cell_count) cells. Sorting only chooses
    # a post-processing cutoff; it does not repair the manufacturing geometry.
    allowed = int(np.floor(run.scenario.volfrac * density.size))
    cutoff = np.sort(density.ravel())[-allowed - 1]
    budget_binary = binary_diagnostic(density, model, max(0.5, cutoff))
    report = {
        "preset": preset, "updater": updater, "shape": density.shape, "iterations": iterations,
        "initial_compliance": initial, "final_compliance": final.objective,
        "comparison_ramp_q": final_q,
        "physical_volume_fraction": float(density.mean()), "volume_limit": run.scenario.volfrac,
        "last_change": method.get_change(),
        "thresholded_volume_fraction": binary["volume_fraction"],
        "thresholded_compliance": binary["compliance"],
        "unsupported_cells_in_one_layer_45_degree_check": binary["unsupported_cells_one_layer_45_degree"],
        "budget_thresholded_diagnostic": budget_binary,
        "gray_fraction_0.1_to_0.9": float(np.mean((density > 0.1) & (density < 0.9))),
    }
    method.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--mesh", type=float, default=1.0)
    parser.add_argument("--updater", choices=("mma", "pymoto_gcmma"), default="mma")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    if not np.isfinite(args.mesh) or args.mesh <= 0:
        parser.error("--mesh must be finite and positive")
    print(json.dumps([validate(p, args.iterations, args.mesh, args.updater)
                      for p in ("MBB Beam", "Cantilever")], indent=2))


if __name__ == "__main__":
    main()
