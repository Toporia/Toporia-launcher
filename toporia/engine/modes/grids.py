# engine/modes/grids.py — what every multi-run mode shares.
#
# A sweep, a comparison and a sensitivity study all do the same three things:
#
#     1. make a folder for the mode's results          mode_folder()
#     2. run variants of one Run, each with a few      run_cells()
#        parameter paths set to new values
#     3. put the resulting images side by side         save_grid()
#
# Keeping them here means each mode file only says what it varies and what it
# draws, and every mode prints and saves the same way.

import time
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from toporia.engine.loop import run_single
from toporia.framework import apply_param


def mode_folder(base_run, name):
    """The folder `name` inside the run's output directory, created if needed."""
    folder = Path(base_run.output.dir) / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def with_values(run, assignments):
    """The run with each (parameter path, value) applied in order; the input is not changed."""
    for path, value in assignments:
        run = apply_param(run, path, value)
    return run


def run_cells(base_run, cells, on_iteration=None):
    """Run one optimisation per cell and print progress.

    `cells` is a list of (assignments, folder): the parameter values to set,
    and where that cell's results go.  `on_iteration` is the GUI's live
    callback, passed through to every run.
    """
    start = time.perf_counter()
    for k, (assignments, folder) in enumerate(cells, 1):
        run = with_values(base_run.with_output_dir(folder), assignments)
        label = " ".join(f"{path}={value:.3g}" for path, value in assignments)
        print(f"[{k}/{len(cells)}] {label}  starting...")
        t0 = time.perf_counter()
        run_single(run, on_iteration)
        print(f"[{k}/{len(cells)}] done"
              f"  run {time.perf_counter() - t0:.1f}s  total {time.perf_counter() - start:.1f}s")
    print(f"total: {time.perf_counter() - start:.1f}s")


# Two looks for a grid of images.  DESIGNS shows final_density.png files as
# greyscale designs at their true aspect ratio; FIGURES shows finished figures
# (a sensitivity plot, with its colour bar) stretched to fill each cell.
DESIGNS = {"pixels_per_inch": 100, "smallest_cell": (3.0, 2.0), "dpi": 180,
           "show": {"cmap": "gray", "vmin": 0, "vmax": 1}, "equal_aspect": True}
FIGURES = {"pixels_per_inch": 120, "smallest_cell": (4.0, 2.5), "dpi": 150,
           "show": {"aspect": "auto"}, "equal_aspect": False}


def save_grid(images, n_rows, n_cols, path, look, fontsize):
    """Lay out `images`, a row-major list of (image path, title), as one PNG; return its path."""
    height, width = mpimg.imread(str(images[0][0])).shape[:2]
    cell_w = max(look["smallest_cell"][0], width / look["pixels_per_inch"])
    cell_h = max(look["smallest_cell"][1], height / look["pixels_per_inch"])
    fig, axes = plt.subplots(n_rows, n_cols, squeeze=False, figsize=(cell_w * n_cols, cell_h * n_rows))
    for ax, (image, title) in zip(axes.flat, images):
        ax.imshow(mpimg.imread(str(image)), **look["show"])
        ax.set_title(title, fontsize=fontsize)
        ax.axis("off")
        if look["equal_aspect"]:
            ax.axis("equal")
    fig.tight_layout()
    fig.savefig(path, dpi=look["dpi"])
    plt.close(fig)        # never pop up as an interactive window
    return path
