# engine/modes/sweep.py — run a grid of optimisations, varying one or two parameters.
#
#   sweep     one parameter, linearly spaced over an n_rows × n_cols grid
#             (e.g. volfrac from 0.08 to 0.60 in a 3 × 3 grid)
#   sweep_2d  two parameters, one along the rows and one along the columns,
#             to see how they interact (e.g. volfrac × mesh resolution m)
#
# Any parameter path works ("volfrac", "interpolation.penal", "filters[1].beta",
# "load_cases[0].Fa"; see framework/problem/run.py).  Each cell is a complete
# run with its own output folder; the final designs are then laid out as one
# image, sweep_grid.png or sweep2d_grid.png.

import numpy as np

from .grids import DESIGNS, mode_folder, run_cells, save_grid


def sweep(parameter, min_val, max_val, n_rows, n_cols, base_config, on_iteration=None):
    """Sweep one parameter over n_rows × n_cols linearly spaced values.

    Results go to <output>/sweep_<parameter>/, one sub-folder per value, and
    the grid image to sweep_grid.png there.  `on_iteration(density,
    objectives, iteration)` is the GUI's live callback.
    """
    folder = mode_folder(base_config, f"sweep_{parameter}")
    values = np.linspace(min_val, max_val, n_rows * n_cols)
    cells = [([(parameter, value)], folder / f"{parameter}_{value:.4f}") for value in values]
    run_cells(base_config, cells, on_iteration)

    images = [(cell_folder / "final_density.png", f"{parameter} = {value:.3g}")
              for value, (_, cell_folder) in zip(values, cells)]
    return save_grid(images, n_rows, n_cols, folder / "sweep_grid.png", DESIGNS, fontsize=9)


def sweep_2d(row_param, row_min, row_max, n_rows,
             col_param, col_min, col_max, n_cols,
             base_config, on_iteration=None):
    """Sweep two parameters at once: `row_param` down the rows, `col_param` across the columns.

    Results go to <output>/sweep2d_<row>_vs_<col>/, and the grid image to
    sweep2d_grid.png there.
    """
    folder = mode_folder(base_config, f"sweep2d_{row_param}_vs_{col_param}")
    pairs = [(row_value, col_value)
             for row_value in np.linspace(row_min, row_max, n_rows)
             for col_value in np.linspace(col_min, col_max, n_cols)]
    cells = [([(row_param, rv), (col_param, cv)], folder / f"{row_param}_{rv:.4f}__{col_param}_{cv:.4f}")
             for rv, cv in pairs]
    run_cells(base_config, cells, on_iteration)

    images = [(cell_folder / "final_density.png", f"{row_param}={rv:.3g}  {col_param}={cv:.3g}")
              for (rv, cv), (_, cell_folder) in zip(pairs, cells)]
    return save_grid(images, n_rows, n_cols, folder / "sweep2d_grid.png", DESIGNS, fontsize=8)
