# sweep_2d.py — 2-D parameter sweep
#
# Like sweep.py but varies TWO parameters simultaneously:
#   - one parameter changes along the rows of the output grid
#   - a different parameter changes along the columns
# This lets you visualise interaction effects between two design variables.
#
# Example: rows = volfrac (0.10 → 0.40),  cols = mesh resolution m (0.4 → 0.75)
# produces a grid where each row is denser material and each column is finer mesh.


import time
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np

from toporia.engine.loop import run_single as _run_single
from toporia.framework import LoadCase, Run, apply_param


def sweep_2d(row_param, row_min, row_max, n_rows,
             col_param, col_min, col_max, n_cols,
             base_config, on_iteration=None):
    """Sweep two parameters independently: one along rows, one along columns.

    on_iteration(density, objectives, iteration) — optional GUI callback.
    """
    row_values = np.linspace(row_min, row_max, n_rows)  # e.g. [0.10, 0.25, 0.40]
    col_values = np.linspace(col_min, col_max, n_cols)
    output_dir = Path(base_config.output.dir) / f"sweep2d_{row_param}_vs_{col_param}"
    output_dir.mkdir(parents=True, exist_ok=True)

    img_paths, t_total, k = {}, time.perf_counter(), 0  # dict indexed by (row, col)

    for i, rv in enumerate(row_values):     # i = row index, rv = row parameter value
        for j, cv in enumerate(col_values): # j = col index, cv = col parameter value
            k += 1
            run_dir = output_dir / f"{row_param}_{rv:.4f}__{col_param}_{cv:.4f}"

            # Chain two apply_param calls: first apply the row param, then the col.
            # Each call returns a NEW config — the original base_config is never mutated.
            cfg = apply_param(
                apply_param(base_config.with_output_dir(run_dir), row_param, rv),
                col_param, cv,
            )
            print(f"[{k}/{n_rows*n_cols}] {row_param}={rv:.3g} {col_param}={cv:.3g}  starting...")
            t0 = time.perf_counter()

            _run_single(cfg, on_iteration)

            img_paths[(i, j)] = cfg.output.dir / "final_density.png"
            print(f"[{k}/{n_rows*n_cols}] done"
                  f"  run {time.perf_counter()-t0:.1f}s  total {time.perf_counter()-t_total:.1f}s")

    # ── Assemble grid image ───────────────────────────────────────────────────
    sample         = mpimg.imread(str(img_paths[(0, 0)]))
    ih, iw         = sample.shape[:2]
    cell_w, cell_h = max(3.0, iw/100), max(2.0, ih/100)
    fig, axes      = plt.subplots(n_rows, n_cols, figsize=(cell_w*n_cols, cell_h*n_rows))
    for i, rv in enumerate(row_values):
        for j, cv in enumerate(col_values):
            ax = axes[i, j] if n_rows > 1 else axes[j]  # axes is 1-D when n_rows==1
            ax.imshow(mpimg.imread(str(img_paths[(i, j)])), cmap="gray", vmin=0, vmax=1)
            ax.set_title(f"{row_param}={rv:.3g}  {col_param}={cv:.3g}", fontsize=8)
            ax.axis("off"); ax.axis("equal")
    fig.tight_layout()
    fig.savefig(output_dir / "sweep2d_grid.png", dpi=180)
    plt.close(fig)
    print(f"total: {time.perf_counter()-t_total:.1f}s")


if __name__ == "__main__":
    # ── Edit these to configure a standalone 2-D sweep ────────────────────────
    BASE_CONFIG = Run().updated(
        m=0.25, volfrac=0.25,
        filter_specs=[{"type": "density"}], max_iter=50, tol=0.05,
        load_cases=[LoadCase(Fmag=1.0, Fa=0.0, weight=0.5),
                    LoadCase(Fmag=1.0, Fa=270.0, weight=0.5)],
        save_every=0,
    )
    sweep_2d("volfrac", 0.1, 0.8, 8, "m", 0.4, 1.5, 4, BASE_CONFIG)
