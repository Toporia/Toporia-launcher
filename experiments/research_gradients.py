"""Directional gradient checks at the designs the showcases actually end at.

python -m experiments.research_gradients [--case NAME]

The batch drivers probe one smooth, grey design near the start. Optimised
designs are where derivatives get hard: nearly 0/1 fields, sharp projections,
stresses beside void, close eigenvalues. This driver loads every saved final
design of the Batch 3 and Batch 4 optimization showcases and, for the
objective, the volume and every further constraint, compares the adjoint
directional derivative with central differences.

Only variables strictly inside their bounds are perturbed: at a bound the
derivative exists from one side only, and an updater never moves past it.
Three steps are tried and every error is recorded; a response passes when the
best step agrees within 1e-4 (relative, or absolute below 1). A design with no
interior variables (TOBS, BESO: every element solid or void) has no two-sided
derivative to check and is reported as such. Stress constraints are probed with
their adaptive scale off, as the batch drivers do: that scale is reset every
evaluation and treated as a constant in the gradient on purpose.
"""

import argparse
import contextlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from toporia.engine.loop import initialized_method
from toporia.framework import Run
from toporia.framework.parts.composition import ComposedMethod
from toporia.plugins.problems import _research_batch3 as batch3
from toporia.plugins.problems import _research_batch4 as batch4

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/research/evidence"
OUTPUT = EVIDENCE / "gradients/report.json"
STEPS = (1e-6, 1e-5, 1e-4)
TOLERANCE = 1e-4
#: Variables closer than this to a bound are held fixed (more than the largest step).
MARGIN = 1e-3


def cases():
    """(batch, name, recipe, saved-variables path) of every optimization showcase."""
    found = []
    for name in batch3.CASES:
        folder = EVIDENCE / "batch3" / name
        if (folder / "final-variables.csv").exists():
            found.append(("batch3", name, batch3.recipe, folder / "final-variables.csv"))
    for name in batch4.CASES:
        folder = EVIDENCE / "batch4" / name
        if (folder / "final-variables.npy").exists():
            found.append(("batch4", name, batch4.recipe, folder / "final-variables.npy"))
    return found


def _fixed_stress_scale(scenario):
    constraints = [dict(spec, adaptive=False) if spec.get("type") == "stress" else spec
                   for spec in scenario.constraints]
    return replace(scenario, constraints=constraints)


def _relative(fd, adjoint):
    return float(abs(fd - adjoint) / max(1.0, abs(fd), abs(adjoint)))


def at_schedule_end(method, solver):
    """Set every scheduled parameter to its last value, as it was when the run ended."""
    for spec in solver.schedules:
        method.set_parameter(spec["path"], spec["end"])


def probe(batch, name, recipe, path):
    """Errors of every response at the saved final design, per step."""
    scenario, solver = recipe(name)
    with contextlib.redirect_stdout(None):
        method = initialized_method(Run(_fixed_stress_scale(scenario), solver))
        at_schedule_end(method, solver)
    try:
        if not isinstance(method, ComposedMethod):
            return dict(batch=batch, case=name, status="not_composed",
                        reason="a standalone method without a separate model to differentiate")
        model = method._model
        start = model.initial_design()
        model.evaluate(start, gradients=False)        # eigenvalue references are set at the start, as in a run
        x = (np.loadtxt(path, delimiter=",") if path.suffix == ".csv" else np.load(path)).reshape(start.shape)
        lower, upper = model.bounds()
        interior = (x > lower + MARGIN) & (x < upper - MARGIN)
        record = dict(batch=batch, case=name, variables=int(x.size), interior=int(interior.sum()))
        if not interior.any():
            return dict(record, status="no_interior",
                        reason="every variable is at a bound: only one-sided derivatives exist")
        direction = np.random.default_rng(4222).normal(size=x.shape) * interior
        direction /= np.linalg.norm(direction)
        base = model.evaluate(x)
        names = ["objective", "volume"] + [f"constraint {i}" for i in range(len(base.constraints))]
        adjoints = [float(np.sum(base.objective_gradient * direction)), float(np.sum(base.volume_gradient * direction))]
        adjoints += [float(np.sum(c.gradient * direction)) for c in base.constraints]
        errors = {key: [] for key in names}
        for h in STEPS:
            high, low = model.evaluate(x + h * direction, gradients=False), model.evaluate(x - h * direction, gradients=False)
            values = [(high.objective, low.objective), (high.volume, low.volume)]
            values += [(a.value, b.value) for a, b in zip(high.constraints, low.constraints, strict=True)]
            for key, adjoint, (a, b) in zip(names, adjoints, values, strict=True):
                errors[key].append(_relative((a - b) / (2 * h), adjoint))
        best = {key: min(values) for key, values in errors.items()}
        failed = [key for key, value in best.items() if not value < TOLERANCE]
        return dict(record, status="failed" if failed else "passed", steps=list(STEPS), errors=errors,
                    best=best, failed=failed)
    finally:
        method.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", help="probe one case (its name in Batch 3 or 4)")
    args = parser.parse_args()
    selected = [c for c in cases() if args.case in (None, c[1])]
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {"cases": []}
    results = {(r["batch"], r["case"]): r for r in previous["cases"]}
    for case in selected:
        record = probe(*case)
        results[(record["batch"], record["case"])] = record
        best = max(record.get("best", {}).values(), default=None)
        print(record["case"], record["status"], "" if best is None else f"worst best-step error {best:.2e}",
              " ".join(record.get("failed", [])), flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(dict(scope=__doc__.split("\n\n", 2)[1].replace("\n", " "), tolerance=TOLERANCE,
                                      cases=sorted(results.values(), key=lambda r: (r["batch"], r["case"]))),
                                 indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
