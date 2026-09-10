# sweep.py — 1-D parameter sweep
#
# Runs the optimisation repeatedly while linearly varying one config parameter
# (e.g. volfrac from 0.08 to 0.60 across a 3×3 image grid).
# Results are saved to disk and assembled into a single summary PNG.
#
# Two ways to use:
#   1. python sweep.py          → uses the config at the bottom of this file
#   2. from toporia.engine.sweep import sweep  → call sweep() from the GUI with any config


import time
from pathlib import Path

import matplotlib.image as mpimg  # reading PNG files back in for grid assembly
import matplotlib.pyplot as plt
import numpy as np

from toporia.core import LoadCase, Run, apply_param
from toporia.engine.runner import run_single as _run_single


def sweep(parameter, min_val, max_val, n_rows, n_cols, base_config,
          on_iteration=None):
    """Sweep one parameter over an n_rows × n_cols grid of linearly spaced values.

    Each cell in the grid is one full optimisation run.  Results are saved under
    output_dir/sweep_<parameter>/ and assembled into sweep_grid.png.

    on_iteration(density, objectives, iteration) — optional GUI callback fired
    after every solver step so the live canvas can update between cells.
    """
    # Build the list of parameter values: e.g. [0.08, 0.155, 0.23, ..., 0.60]
    values     = np.linspace(min_val, max_val, n_rows * n_cols)
    output_dir = Path(base_config.output.dir) / f"sweep_{parameter}"
    output_dir.mkdir(parents=True, exist_ok=True)  # create folder, ignore if exists

    img_paths, t_total = [], time.perf_counter()   # accumulate PNG paths + start timer

    for k, value in enumerate(values, 1):          # k goes 1, 2, 3, ...
        # apply_param returns a NEW config with:
        #   - a unique output_dir for this cell's results
        #   - the swept parameter set to the current value
        # It handles both plain fields ("volfrac") and load-case fields ("lc0.Fmag").
        cfg = apply_param(
            base_config.with_output_dir(output_dir / f"{parameter}_{value:.4f}"),
            parameter, value,
        )
        print(f"[{k}/{len(values)}] {parameter}={value:.3g}  starting...")
        t0 = time.perf_counter()

        _run_single(cfg, on_iteration)

        img_paths.append((cfg.output.dir / "final_density.png", value))
        print(f"[{k}/{len(values)}] done"
              f"  run {time.perf_counter()-t0:.1f}s  total {time.perf_counter()-t_total:.1f}s")

    # ── Assemble the individual PNGs into one summary grid image ──────────────
    sample         = mpimg.imread(str(img_paths[0][0]))     # read one to get pixel dims
    ih, iw         = sample.shape[:2]
    cell_w, cell_h = max(3.0, iw/100), max(2.0, ih/100)    # subplot size in inches
    fig, axes      = plt.subplots(n_rows, n_cols, figsize=(cell_w*n_cols, cell_h*n_rows))
    for ax, (img_path, value) in zip(np.array(axes).flat, img_paths):
        ax.imshow(mpimg.imread(str(img_path)), cmap="gray", vmin=0, vmax=1)
        ax.set_title(f"{parameter} = {value:.3g}", fontsize=9)
        ax.axis("off"); ax.axis("equal")
    fig.tight_layout()
    fig.savefig(output_dir / "sweep_grid.png", dpi=180)
    plt.close(fig)    # close so it doesn't pop up as an interactive window
    print(f"total: {time.perf_counter()-t_total:.1f}s")


if __name__ == "__main__":
    # ── Edit these values to configure a standalone sweep ─────────────────────
    BASE_CONFIG = Run().updated(
        m=0.5, volfrac=0.25,
        filter_specs=[{"type": "density"}], max_iter=50, tol=0.05,
        load_cases=[LoadCase(Fmag=1.0, Fa=0.0, weight=0.5),
                    LoadCase(Fmag=1.0, Fa=270.0, weight=0.5)],
        save_every=0,
    )
    sweep("volfrac", 0.08, 0.60, 3, 3, BASE_CONFIG)
