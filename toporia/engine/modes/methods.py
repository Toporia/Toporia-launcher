# engine/modes/methods.py — several methods on the same problem: which does best?
#
#   compare_methods   run each method on one scenario, mesh and stopping rule;
#                     one image of every final design, one table of numbers
#   benchmark         the same over several problems: the comparison Toporia
#                     exists to make, with only the method varying
#   sweep_methods     the methods down the rows, one setting swept across the
#                     columns: how each optimiser reacts to that setting
#
# Every method is held to the same scenario, mesh, filters, iteration limit and
# tolerance; only the method and its own parameters change.  A method that
# cannot solve the scenario (it cannot enforce a constraint, or a package it
# needs is not installed) is listed with the reason rather than stopping the
# comparison.
#
# The run's post-processors (output.postprocess) run on every method's design
# alike, and their numbers become further columns: with a threshold, the
# compliance of every design cut to black and white at its own volume.
#
# The table keeps each method's objective and a common SIMP-p=3 compliance
# measurement (Q4/H8, retaining springs; scalar conduction for heat). The grid
# shows the relevant objective metric, including displacement and frequency.
# Grey level is 4/n Σ ρ(1 − ρ): zero for binary material, one for uniform grey.
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
from toporia.engine.postprocess import table_metrics
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.postprocessors import _measure as measure

from .grids import DESIGNS, mode_folder, save_grid, with_values

#: The referee measures every final design with the same physics.
REFEREE_PENAL = measure.REFEREE_PENAL
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
                           f"{row['method']}\n{_design_metric(row)}"))

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
    {"m": 0.5, "max_iter": 80, "interpolation.penal": 4}; the
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


def sweep_methods(methods, parameter, min_val, max_val, n_values, base_config, on_iteration=None):
    """Every method in `methods` at `n_values` linearly spaced values of `parameter`.

    The grid has one row per method and one column per value; a method that
    cannot solve the problem fills its row with the reason.  Returns (path of
    methods_sweep_grid.png, rows), one row per cell with the COLUMNS and the
    swept parameter's value.  Results go to <output>/sweep_methods_<parameter>/.
    """
    folder = mode_folder(base_config, f"sweep_methods_{parameter}")
    methods = list(dict.fromkeys(methods))
    values = np.linspace(min_val, max_val, n_values)
    rows, images = [], []
    for i, name in enumerate(methods):
        for j, value in enumerate(values):
            print(f"\n=== [{i * len(values) + j + 1}/{len(methods) * len(values)}] {name}, {parameter} = {value:.4g} ===")
            run = with_values(base_config, [(parameter, value)])
            cell = folder / f"{parameter}_{value:.4f}"
            row = _run_method(name, run, cell, on_iteration)
            row[parameter] = float(value)
            rows.append(row)
            title = f"{row['method']}   {parameter} = {value:.3g}"
            if row["status"] == "ran":
                images.append((cell / _folder_name(row["method"]) / "final_density.png",
                               f"{title}\n{_design_metric(row)}"))
            else:
                images.append((None, f"{title}\nskipped: {row['stop_reason']}"))

    _write_table(rows, folder / "methods_sweep.csv")
    print("\n" + format_table(rows))
    grid = None
    if any(image is not None for image, _ in images):
        grid = save_grid(images, len(methods), len(values), folder / "methods_sweep_grid.png", DESIGNS, fontsize=7)
        print(f"\nSaved methods x {parameter} grid -> {grid}")
    return grid, rows


# ── One method ────────────────────────────────────────────────────────────────

def _design_metric(row):
    if "output_displacement" in row:
        return f"Output displacement = {row['output_displacement']:.4g}"
    if "omega_1" in row:
        return f"Fundamental frequency = {row['omega_1']:.4g} rad/s"
    if "thermal_compliance" in row:
        return f"Thermal compliance = {row['thermal_compliance']:.4g}"
    if "objective_type" in row and row["objective_type"] not in ("compliance", "end_compliance"):
        return f"Objective = {row['objective']:.4g}"
    return f"C = {row['referee_compliance']:.4g}"


def _comparison_run(method_cls, base_config):
    """Apply this method's identity and only its declared parameters."""
    own = {p.name for p in method_cls.params}
    params = {key: value for key, value in base_config.solver.method_params.items() if key in own}
    return base_config.updated(method=method_cls.name, method_params=params)


def comparison_problems(method_cls, base_config, *, missing=None):
    """Shared preflight for comparison selectors and the actual comparison run."""
    from toporia.engine.pipeline import solver_problems
    from toporia.framework.registry import install_hint, missing_dependencies

    scenario_reasons = method_cls.capabilities.problems_with(base_config.scenario)
    if scenario_reasons:
        return scenario_reasons
    if missing is None:
        missing = missing_dependencies(method_cls)
    if missing:
        return [f"not installed: {install_hint(missing)}"]
    run = _comparison_run(method_cls, base_config)
    return solver_problems(method_cls, run)


def _run_method(name, base_config, folder, on_iteration):
    """Run one method on the base problem, or say why it cannot; return its table row."""
    from toporia.plugins.methods import method_class

    method_cls = method_class(name)
    row = dict.fromkeys(COLUMNS)
    row.update(method=method_cls.name, label=method_cls.label)
    reasons = comparison_problems(method_cls, base_config)
    if reasons:
        row.update(status="skipped", stop_reason="; ".join(reasons))
        print(f"  skipped: {row['stop_reason']}")
        return row

    # Keep only the parameters this method declares, so one method's settings
    # (chosen in the GUI for another) never stop another method's run.
    run = _comparison_run(method_cls, base_config).with_output_dir(folder / _folder_name(method_cls.name))
    start = time.perf_counter()
    store, density = run_single_with_store(run, on_iteration)
    final = {key: values[-1] for key, values in store.responses.items()}
    # The study's geometric volume stays comparable across methods; SINH also
    # exposes the effective volume actually constrained by its optimiser.
    if "effective_volume_fraction" in final:
        row["effective_volume"] = final["effective_volume_fraction"]
    row.update(table_metrics(store.postprocess))     # e.g. threshold.compliance, the same for every method
    if "output_displacement" in final:
        row["output_displacement"] = final["output_displacement"]
    objective_type = run.scenario.objective.get("type", "compliance")
    if objective_type == "eigenfrequency" and "omega_1" in final:
        row["omega_1"] = final["omega_1"]
    elif objective_type == "thermal_compliance":
        row["thermal_compliance"] = final["objective"]
    elif objective_type not in ("compliance", "end_compliance", "output_displacement"):
        row["objective_type"] = objective_type
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
    """Compliance of a final design measured the same way for every method (plugins/postprocessors/_measure.py)."""
    return measure.referee_compliance(make_problem(run.scenario, run.solver.m), density,
                                      heat_source=run.solver.method_params.get("heat_source"))


grey_level = measure.grey_level


# ── The table ─────────────────────────────────────────────────────────────────

def format_table(rows):
    """The rows as an aligned text table for the console and the GUI's log."""
    shown = ("problem", "method", "status", "referee_compliance", "objective", "volume",
             "grey_level", "iterations", "solves", "seconds", "feasible")
    if not any(row.get("problem") for row in rows):
        shown = shown[1:]
    shown += tuple(_extra_columns(rows))          # the post-processors' numbers

    def cell(value):
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value)

    table = [list(shown)] + [[cell(row.get(column)) for column in shown] for row in rows]
    widths = [max(len(line[i]) for line in table) for i in range(len(shown))]
    lines = ["  ".join(text.ljust(width) for text, width in zip(line, widths, strict=True)) for line in table]
    lines.insert(1, "  ".join("-" * width for width in widths))
    skipped = [row for row in rows if row["status"] == "skipped"]
    lines += [f"  {row['method']}: {row['stop_reason']}" for row in skipped]
    return "\n".join(lines)


def _extra_columns(rows):
    """Columns beyond COLUMNS that some row has (post-processor metrics), in the order first seen."""
    return list(dict.fromkeys(key for row in rows for key in row if key not in COLUMNS))


def _write_table(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(COLUMNS) + _extra_columns(rows))
        writer.writeheader()
        writer.writerows(rows)


def _folder_name(text):
    """A folder-safe version of a method or problem name."""
    return "".join(c if c.isalnum() or c in "+-_." else "_" for c in text)
