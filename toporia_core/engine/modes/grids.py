# toporia_core/engine/modes/grids.py — what every multi-run mode shares.
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

import contextlib
import io
import os
import textwrap
import time
from pathlib import Path

from toporia_core.engine.loop import run_single


def mode_folder(base_run, name):
    """The folder `name` inside the run's output directory, created if needed."""
    folder = Path(base_run.output.dir) / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def with_values(run, assignments):
    """The run with each (path, value) applied in order — a parameter path or a choice of part
    (toporia_core/engine/modes/choices.py); the input is not changed."""
    from .choices import assign
    for path, value in assignments:
        run = assign(run, path, value)
    return run


def label_of(assignments):
    """The assignments as a cell's label: "volfrac=0.4 choice:updater=mma"."""
    from .choices import show
    return " ".join(f"{path}={show(value)}" for path, value in assignments)


def runnable(base_run, cells):
    """Split cells into those that can run and {folder: why not} for those that cannot."""
    from .choices import problems
    good, skipped = [], {}
    for assignments, folder in cells:
        try:
            reasons = problems(with_values(base_run, assignments))
        except ValueError as error:
            reasons = [str(error)]
        if reasons:
            skipped[folder] = "; ".join(reasons)
        else:
            good.append((assignments, folder))
    return good, skipped


#: Below this many cells a grid runs one cell after another: starting processes costs more.
PARALLEL_FROM = 3

#: Environment variables that make numerical libraries use one thread, so parallel cells
#: share the cores instead of fighting over them.
ONE_THREAD = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def workers_for(cells):
    """How many processes to run `cells` cells in: TOPORIA_WORKERS, else one fewer than the cores."""
    setting = os.environ.get("TOPORIA_WORKERS")
    if setting:
        return max(1, min(int(setting), cells))
    if cells < PARALLEL_FROM:
        return 1
    return max(1, min((os.cpu_count() or 1) - 1, cells))


def _run_cell(run):
    """One cell in a worker process; its console output is returned, not interleaved."""
    output = io.StringIO()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(output):
        run_single(run)
    return time.perf_counter() - t0, output.getvalue()


def run_cells(base_run, cells, on_iteration=None):
    """Run one optimisation per cell and print progress.

    `cells` is a list of (assignments, folder): the parameter values to set,
    and where that cell's results go.  `on_iteration` is the GUI's live
    callback, passed through to every run.

    Cells are independent, so a grid of PARALLEL_FROM or more runs them in
    parallel processes (one fewer than the cores; TOPORIA_WORKERS=n to choose,
    1 for one after another).  Each cell writes its own folder as it would
    alone, so the results are the same; only the live view of every
    iteration is given up for a line per finished cell.
    """
    workers = workers_for(len(cells))
    if workers > 1:
        _run_cells_parallel(base_run, cells, workers)
        return
    start = time.perf_counter()
    for k, (assignments, folder) in enumerate(cells, 1):
        run = with_values(base_run.with_output_dir(folder), assignments)
        label = label_of(assignments)
        print(f"[{k}/{len(cells)}] {label}  starting...")
        t0 = time.perf_counter()
        run_single(run, on_iteration)
        print(f"[{k}/{len(cells)}] done"
              f"  run {time.perf_counter() - t0:.1f}s  total {time.perf_counter() - start:.1f}s")
    print(f"total: {time.perf_counter() - start:.1f}s")


def _run_cells_parallel(base_run, cells, workers):
    # From the submodules: concurrent.futures loads these names lazily, which a bundled
    # (frozen) program cannot resolve on Python 3.15.
    from concurrent.futures._base import as_completed
    from concurrent.futures.process import ProcessPoolExecutor
    start = time.perf_counter()
    print(f"{len(cells)} runs in {workers} parallel processes")
    saved = {name: os.environ.get(name) for name in ONE_THREAD}
    os.environ.update(dict.fromkeys(ONE_THREAD, "1"))     # inherited by the worker processes
    try:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs = {}
            for k, (assignments, folder) in enumerate(cells, 1):
                run = with_values(base_run.with_output_dir(folder), assignments)
                label = label_of(assignments)
                jobs[pool.submit(_run_cell, run)] = (k, label)
            for done, job in enumerate(as_completed(jobs), 1):
                k, label = jobs[job]
                seconds, _ = job.result()             # an error in a cell stops the grid here
                print(f"[{done}/{len(cells)}] {label} done  run {seconds:.1f}s"
                      f"  total {time.perf_counter() - start:.1f}s", flush=True)
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    print(f"total: {time.perf_counter() - start:.1f}s")


# Two looks for a grid of images.  DESIGNS shows final_density.png files as
# greyscale designs at their true aspect ratio; FIGURES shows finished figures
# (a sensitivity plot, with its colour bar) stretched to fill each cell.
DESIGNS = {"pixels_per_inch": 100, "smallest_cell": (3.0, 2.0), "dpi": 180,
           "show": {"cmap": "gray", "vmin": 0, "vmax": 1}, "equal_aspect": True}
FIGURES = {"pixels_per_inch": 120, "smallest_cell": (4.0, 2.5), "dpi": 150,
           "show": {"aspect": "auto"}, "equal_aspect": False}


def save_grid(images, n_rows, n_cols, path, look, fontsize):
    """Lay out `images`, a row-major list of (image path, title), as one PNG; return its path.

    An image path of None leaves its cell empty but for the title, written across the
    middle of the cell (a run that was skipped, and why).
    """
    from toporia_core.engine.plotting import pyplot
    plt = pyplot()
    if plt is None:
        return None
    first = next((image for image, _ in images if image is not None), None)   # every cell may be skipped
    height, width = plt.imread(str(first)).shape[:2] if first is not None else (200, 300)
    cell_w = max(look["smallest_cell"][0], width / look["pixels_per_inch"])
    cell_h = max(look["smallest_cell"][1], height / look["pixels_per_inch"])
    fig, axes = plt.subplots(n_rows, n_cols, squeeze=False, figsize=(cell_w * n_cols, cell_h * n_rows))
    for ax, (image, title) in zip(axes.flat, images, strict=False):
        if image is None:
            ax.text(0.5, 0.5, "\n".join(textwrap.fill(line, 38) for line in title.split("\n")),
                    ha="center", va="center", fontsize=fontsize, color="gray", transform=ax.transAxes)
        else:
            ax.imshow(plt.imread(str(image)), **look["show"])
            ax.set_title(title, fontsize=fontsize)
        ax.axis("off")
        if look["equal_aspect"]:
            ax.axis("equal")
    for ax in list(axes.flat)[len(images):]:          # a grid larger than the list of values
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=look["dpi"])
    plt.close(fig)        # never pop up as an interactive window
    return path
