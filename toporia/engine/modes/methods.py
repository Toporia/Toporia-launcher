# engine/modes/methods.py — several methods on the same problem: which does best?
#
#   compare_methods   run each method on one scenario, mesh and stopping rule;
#                     one image of every final design, one table of numbers
#   benchmark         the same over several problems: the comparison Toporia
#                     exists to make, with only the method varying
#
# Every method is held to the same scenario, mesh, filters, iteration limit and
# tolerance; only the method and its own parameters change.  A method that
# cannot solve the scenario (it cannot enforce a constraint, or a package it
# needs is not installed) is listed with the reason rather than stopping the
# comparison.
#
# The table reports each method's own objective, and also a referee: the
# compliance of every final design measured the same way, on Toporia's Q4
# solver with SIMP p = 3 and no filter.  Methods use different physics (the
# pyMOTO model), penalties or interpolations (the level set is linear), so
# their own objectives are not on one scale; the referee is.  The grey level
# (Sigmund 2007: 4/n Σ ρ(1 − ρ), 0 for black and white, 1 for uniform grey)
# says how crisp each design is.
#
# Output, in <output>/compare_methods/ (or one folder per problem for a benchmark):
#   <method>/        each method's own run: final_density.png, run.json, ...
#   methods_grid.png the final designs side by side
#   methods.csv      the table

import csv
import time
from pathlib import Path

import numpy as np

from toporia.engine.loop import run_single_with_store
from toporia.framework.problem.mesh import RectangularProblem

from .grids import DESIGNS, mode_folder, save_grid, with_values

#: The referee measures every final design with the same physics.
REFEREE_PENAL = 3.0
#: The table's columns, in order.
COLUMNS = ("problem", "method", "label", "status", "objective", "referee_compliance", "volume",
           "grey_level", "iterations", "solves", "seconds", "feasible", "stop_reason")


def compare_methods(methods, base_config, on_iteration=None, problem_name=""):
    """Run every method in `methods` (names) on `base_config`'s problem.

    Returns (path of methods_grid.png or None, rows): one row per method, a
    dict with the COLUMNS.  `on_iteration` is the GUI's live callback.
    """
    folder = mode_folder(base_config, "compare_methods")
    methods = list(dict.fromkeys(methods))     # each method once, in the order given
    rows, images = [], []
    for k, name in enumerate(methods, 1):
        print(f"\n=== [{k}/{len(methods)}] {name} ===")
        row = _run_method(name, base_config, folder, on_iteration)
        row["problem"] = problem_name
        rows.append(row)
        if row["status"] == "ran":
            images.append((folder / _folder_name(row["method"]) / "final_density.png",
                           f"{row['label']}\nC = {row['referee_compliance']:.4g}"))

    _write_table(rows, folder / "methods.csv")
    print("\n" + format_table(rows))
    grid = None
    if images:
        n_cols = min(4, len(images))
        n_rows = -(-len(images) // n_cols)
        grid = save_grid(images, n_rows, n_cols, folder / "methods_grid.png", DESIGNS, fontsize=8)
        print(f"\nSaved comparison grid -> {grid}")
    return grid, rows


def benchmark(methods, problems, overrides=None, output_dir=None, on_iteration=None):
    """compare_methods on every named problem preset; returns all rows.

    `overrides` ({parameter path: value}) are applied to every problem, e.g.
    {"m": 0.5, "max_iter": 80, "method.penal": 4}; the
    results go to <output_dir>/<problem>/compare_methods/, and the combined
    table to <output_dir>/benchmark.csv.
    """
    from toporia.plugins.problems import get_run
    output_dir = Path(output_dir) if output_dir else None
    all_rows = []
    for problem in problems:
        run = with_values(get_run(problem), (overrides or {}).items())
        if output_dir is not None:
            run = run.with_output_dir(output_dir / _folder_name(problem))
        print(f"\n##### {problem} #####")
        _, rows = compare_methods(methods, run, on_iteration, problem_name=problem)
        all_rows += rows
    if output_dir is not None:
        _write_table(all_rows, output_dir / "benchmark.csv")
    print("\n" + format_table(all_rows))
    return all_rows


# ── One method ────────────────────────────────────────────────────────────────

def _run_method(name, base_config, folder, on_iteration):
    """Run one method on the base problem, or say why it cannot; return its table row."""
    from toporia.framework.registry import install_hint, missing_dependencies
    from toporia.plugins.methods import method_class

    method_cls = method_class(name)
    row = dict.fromkeys(COLUMNS)
    row.update(method=method_cls.name, label=method_cls.label)
    missing = missing_dependencies(method_cls)
    reasons = method_cls.capabilities.problems_with(base_config.scenario)
    if missing:
        reasons = [f"not installed: {install_hint(missing)}"]
    if reasons:
        row.update(status="skipped", stop_reason="; ".join(reasons))
        print(f"  skipped: {row['stop_reason']}")
        return row

    # Keep only the parameters this method declares, so one method's settings
    # (chosen in the GUI for another) never stop another method's run.
    own = {p.name for p in method_cls.params}
    params = {key: value for key, value in base_config.solver.method_params.items() if key in own}
    run = (base_config.with_output_dir(folder / _folder_name(method_cls.name))
           .updated(method=method_cls.name, method_params=params))
    start = time.perf_counter()
    store, density = run_single_with_store(run, on_iteration)
    final = {key: values[-1] for key, values in store.responses.items()}
    row.update(
        status="ran",
        objective=final.get("objective"),
        referee_compliance=referee_compliance(run, density),
        volume=float(density.mean()),
        grey_level=grey_level(density),
        iterations=len(store.objectives),
        solves=final.get("solves"),
        seconds=round(time.perf_counter() - start, 2),
        feasible=all(entry["satisfied"] is not False for entry in store.limits),
        stop_reason=store.stop_reason,
    )
    return row


def referee_compliance(run, density):
    """Compliance of a final design measured the same way for every method.

    Toporia's Q4 solver, SIMP with p = REFEREE_PENAL, no filter, the
    scenario's load cases and weights; the density is clipped to the
    problem's bounds so holes stay holes.
    """
    from toporia.plugins.physics.q4_plane_stress import Q4PlaneStress
    problem = RectangularProblem(run.scenario, run.solver.m)
    engine = Q4PlaneStress()
    engine.initialize(problem, {"penal": REFEREE_PENAL})
    state = engine.solve(np.clip(density, problem.lower_bound, problem.upper_bound))
    return float(sum(weight * engine.compliance(state, case) for case, weight in enumerate(state.weights)))


def grey_level(density):
    """Sigmund's measure of non-discreteness, 4/n Σ ρ(1 − ρ): 0 is black and white, 1 uniform grey."""
    return float(4.0 * np.mean(density * (1.0 - density)))


# ── The table ─────────────────────────────────────────────────────────────────

def format_table(rows):
    """The rows as an aligned text table for the console and the GUI's log."""
    shown = ("problem", "method", "status", "referee_compliance", "objective", "volume",
             "grey_level", "iterations", "solves", "seconds", "feasible")
    if not any(row.get("problem") for row in rows):
        shown = shown[1:]

    def cell(value):
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value)

    table = [list(shown)] + [[cell(row.get(column)) for column in shown] for row in rows]
    widths = [max(len(line[i]) for line in table) for i in range(len(shown))]
    lines = ["  ".join(text.ljust(width) for text, width in zip(line, widths)) for line in table]
    lines.insert(1, "  ".join("-" * width for width in widths))
    skipped = [row for row in rows if row["status"] == "skipped"]
    lines += [f"  {row['method']}: {row['stop_reason']}" for row in skipped]
    return "\n".join(lines)


def _write_table(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _folder_name(text):
    """A folder-safe version of a method or problem name."""
    return "".join(c if c.isalnum() or c in "+-_." else "_" for c in text)
