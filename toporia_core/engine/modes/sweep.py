# toporia_core/engine/modes/sweep.py — run a grid of optimisations, varying one or two things.
#
#   sweep     one variable over an n_rows × n_cols grid: a parameter, linearly spaced
#             (e.g. volfrac from 0.08 to 0.60 in a 3 × 3 grid), or a list of values
#   sweep_2d  two variables, one along the rows and one along the columns, to see how they
#             interact (e.g. volfrac × mesh resolution m, or updater × volfrac)
#
# A variable is any parameter path ("volfrac", "interpolation.penal", "filters[1].beta",
# "load_cases[0].Fa"; see toporia_core/framework/problem/run.py) or a choice of part
# ("choice:updater", "choice:model", "choice:method", "choice:interpolation",
# "choice:representation", "choice:filters[i]"; see choices.py), given as a list of options:
# a discrete variable, so a sweep can be Compare Methods along one axis and a parameter study
# along the other.  Each cell is a complete run with its own output folder; a combination that
# cannot run is left out and its cell says why.  The final designs are laid out as one image,
# sweep_grid.png or sweep2d_grid.png.

import numpy as np

from .choices import choice_label, is_choice, show
from .grids import DESIGNS, mode_folder, run_cells, runnable, save_grid


def _name(path):
    """A path as a folder name: "choice:filters[0]" → "filter_1", "volfrac" → "volfrac"."""
    return choice_label(path).replace(" ", "_") if is_choice(path) else path


def _values(path, low, high, count, values):
    if values is not None:
        return list(values)
    if is_choice(path):
        raise ValueError(f"{path} is a choice of part: give its options as values, not a range")
    return list(np.linspace(low, high, count))


def _run_grid(base_config, cells, on_iteration):
    good, skipped = runnable(base_config, cells)
    for folder, why in skipped.items():
        print(f"  skipped {folder.name}: {why}")
    if good:
        run_cells(base_config, good, on_iteration)
    return skipped


def sweep(parameter, min_val, max_val, n_rows, n_cols, base_config, on_iteration=None, values=None):
    """Sweep one variable over an n_rows × n_cols grid.

    A parameter path is spaced linearly from min_val to max_val; `values` (a list) sets the
    values instead, and is required for a choice of part.  Results go to
    <output>/sweep_<name>/, one sub-folder per value, and the grid image to sweep_grid.png
    there.  `on_iteration(density, objectives, iteration)` is the GUI's live callback.
    """
    folder = mode_folder(base_config, f"sweep_{_name(parameter)}")
    values = _values(parameter, min_val, max_val, n_rows * n_cols, values)
    cells = [([(parameter, value)], folder / f"{_name(parameter)}_{show(value)}") for value in values]
    skipped = _run_grid(base_config, cells, on_iteration)

    images = [(None if cell_folder in skipped else cell_folder / "final_density.png",
               f"{choice_label(parameter) if is_choice(parameter) else parameter} = {show(value)}"
               + (f"\n(not run: {skipped[cell_folder]})" if cell_folder in skipped else ""))
              for value, (_, cell_folder) in zip(values, cells, strict=True)]
    rows = max(n_rows, -(-len(values) // max(n_cols, 1)))
    return save_grid(images, rows, n_cols, folder / "sweep_grid.png", DESIGNS, fontsize=9)


def sweep_2d(row_param, row_min, row_max, n_rows,
             col_param, col_min, col_max, n_cols,
             base_config, on_iteration=None, row_values=None, col_values=None):
    """Sweep two variables at once: `row_param` down the rows, `col_param` across the columns.

    Either may be a choice of part with its options in row_values / col_values (the grid then
    has one row or column per option).  Results go to <output>/sweep2d_<row>_vs_<col>/, and the
    grid image to sweep2d_grid.png there.
    """
    row_values = _values(row_param, row_min, row_max, n_rows, row_values)
    col_values = _values(col_param, col_min, col_max, n_cols, col_values)
    folder = mode_folder(base_config, f"sweep2d_{_name(row_param)}_vs_{_name(col_param)}")
    pairs = [(rv, cv) for rv in row_values for cv in col_values]
    cells = [([(row_param, rv), (col_param, cv)],
              folder / f"{_name(row_param)}_{show(rv)}__{_name(col_param)}_{show(cv)}") for rv, cv in pairs]
    skipped = _run_grid(base_config, cells, on_iteration)

    def title(path, value):
        return f"{choice_label(path) if is_choice(path) else path}={show(value)}"

    images = [(None if cell_folder in skipped else cell_folder / "final_density.png",
               f"{title(row_param, rv)}  {title(col_param, cv)}"
               + (f"\n(not run: {skipped[cell_folder]})" if cell_folder in skipped else ""))
              for (rv, cv), (_, cell_folder) in zip(pairs, cells, strict=True)]
    return save_grid(images, len(row_values), len(col_values), folder / "sweep2d_grid.png", DESIGNS, fontsize=8)
