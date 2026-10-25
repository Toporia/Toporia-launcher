"""Bounded, unregistered, gradient-free simulated-annealing experiment.

Run from the repository root: python -m experiments.simulated_annealing
No topASA code is copied (its repository states no licence). This own standard
Metropolis baseline is not a reproduction or assessment of adaptive topASA.
Random pair transfers propose material redistribution; a scalar shift restores
the actual model volume without using a physics sensitivity. The feasibility
repair makes this an optimisation heuristic, not an exact equilibrium sampler.

S. Kirkpatrick, C. D. Gelatt, M. P. Vecchi, Science 220 (1983) 671-680.
Papers: https://doi.org/10.1126/science.220.4598.671
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class AnnealingResult:
    design: np.ndarray
    objective: float
    evaluations: int
    accepted: int
    history: list


def anneal(model, budget=200, seed=0, step=0.2, temperature=0.05, final_temperature=1e-5):
    """Best bound/volume-feasible design within at most `budget` value-only solves.

    Additional scenario constraints are outside this benchmark's scope.
    """
    if int(budget) != budget or budget < 1:
        raise ValueError("budget must be a positive integer")
    controls = [step, temperature, final_temperature]
    if not np.all(np.isfinite(controls)) or min(controls) <= 0:
        raise ValueError("step and temperatures must be finite and positive")
    lower, upper = (np.asarray(bound, dtype=float) for bound in model.bounds())
    free = np.flatnonzero(upper.ravel() > lower.ravel())
    if model.volume_of(lower) > model.volume_limit + 1e-10:
        raise ValueError("the volume budget is infeasible even at the lower bounds")

    def feasible(trial):
        # Scalar water filling: cheap volume checks only, no FE solve or adjoint.
        lo, hi = float(np.min(lower - trial)), float(np.max(upper - trial))
        best = lower.copy()
        for _ in range(45):
            shift = 0.5 * (lo + hi)
            candidate = np.clip(trial + shift, lower, upper)
            if model.volume_of(candidate) > model.volume_limit:
                hi = shift
            else:
                lo, best = shift, candidate
        return best

    rng = np.random.default_rng(seed)
    current = feasible(np.clip(model.initial_design(), lower, upper))
    value = float(model.evaluate(current, gradients=False).objective)
    if not np.isfinite(value):
        raise ValueError("initial objective is not finite")
    best, best_value = current.copy(), value
    scale = max(abs(value), 1e-12)
    history, accepted, evaluations = [value], 0, 1
    if free.size < 2:
        return AnnealingResult(best, best_value, evaluations, accepted, history)
    for index in range(1, int(budget)):
        trial = current.copy()
        a, b = rng.choice(free, 2, replace=False)
        transfer = rng.uniform(-step, step)
        trial.flat[a] += transfer
        trial.flat[b] -= transfer
        trial = feasible(trial)
        proposed = float(model.evaluate(trial, gradients=False).objective)
        evaluations += 1
        fraction = index / max(1, budget - 1)
        temp = scale * temperature * (final_temperature / temperature) ** fraction
        delta = proposed - value
        if np.isfinite(proposed) and (delta <= 0 or np.log(max(rng.random(), 1e-300)) < -delta / temp):
            current, value = trial, proposed
            accepted += 1
        if np.isfinite(proposed) and proposed < best_value:
            best, best_value = trial.copy(), proposed
        history.append(best_value)
    return AnnealingResult(best, best_value, evaluations, accepted, history)


def main():
    from toporia.checks.common import iterate
    from toporia.engine.loop import initialized_method
    from toporia.plugins.problems import get_run

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budgets", nargs="+", type=int, default=[200, 2000])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--out", type=Path, default=Path("results/annealing-evaluation"))
    args = parser.parse_args()
    if not args.budgets or min(args.budgets) < 1:
        parser.error("budgets must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    run = get_run("MBB Beam").updated(m=0.4, method="q4+oc", max_iter=200, tol=0.01, save_every=0)
    method = initialized_method(run)
    try:
        iterate(method, 200, tol=0.01)
        reference = float(method._model.evaluate(method.x, gradients=False).objective)
        reference_solves = method.solves
        rows = []
        for budget in args.budgets:
            for seed in args.seeds:
                result = anneal(method._model, budget=budget, seed=seed)
                row = {"budget": budget, "seed": seed, "evaluations": result.evaluations,
                       "objective": result.objective, "gap_percent": 100 * (result.objective / reference - 1),
                       "volume": float(method._model.physical(result.design).mean()),
                       "accepted": result.accepted, "within_10_percent": result.objective <= 1.10 * reference,
                       "history": result.history}
                rows.append(row)
                np.save(args.out / f"density-budget{budget}-seed{seed}.npy", method._model.physical(result.design))
                print(json.dumps({key: value for key, value in row.items() if key != "history"}), flush=True)
        report = {"problem": "MBB Beam", "m": 0.4, "shape": list(method.problem.shape),
                  "reference": {"method": "q4+oc", "objective": reference, "solves": reference_solves},
                  "runs": rows}
        (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    finally:
        method.close()


if __name__ == "__main__":
    main()
