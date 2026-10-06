# engine/modes/sensitivity.py — where in the design does a parameter matter?
#
#   sensitivity_field     two runs, at base and base + gap, and per element
#                         (ρ_perturbed − ρ_base) / gap, drawn over the base design
#   sensitivity_sweep     that field for every cell of a one-parameter sweep
#   sensitivity_sweep_2d  ... of a two-parameter sweep
#
# A sweep may also vary the sensitivity study itself, through two special
# paths: "sens.base_value" (where the derivative is taken) and "sens.gap"
# (the finite-difference step).
#
# The figure, sensitivity.png, shows the base design as a faint grey ghost
# with the sensitivity on top in blue–white–red:
#
#   red    more material where the parameter increases
#   blue   less material where the parameter increases
#   white  no change
#
# The overlay's opacity is material presence × sensitivity magnitude, capped
# at 75 %, so elements that do not respond show the base design unchanged and
# the base always shows through.  sensitivity.csv holds the raw numbers.

import csv
import time

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

from toporia.engine.loop import run_single
from toporia.framework import apply_param, projection

from .grids import FIGURES, mode_folder, save_grid

#: Sweep paths that change the sensitivity study instead of the run.
BASE_VALUE, GAP = "sens.base_value", "sens.gap"


def sensitivity_field(param_key, base_value, gap, base_config, on_iteration=None):
    """The per-element sensitivity of the final density to one parameter path.

    Returns (path of sensitivity.png, the sensitivity array, shaped like the design).
    """
    folder = mode_folder(base_config, f"sensitivity_{param_key}_{base_value:.4g}_d{gap:+.4g}")
    densities = []
    for label, value in (("base", base_value), ("perturbed", base_value + gap)):
        run = apply_param(base_config.with_output_dir(folder / f"run_{label}"), param_key, value)
        print(f"\n=== Run {label}: {param_key} = {value:.4g} ===")
        densities.append(run_single(run, on_iteration))

    density_base, density_perturbed = densities
    sensitivity = (density_perturbed - density_base) / gap
    _save_csv(sensitivity, param_key, base_value, gap, folder)
    return _save_figure(density_base, sensitivity, param_key, base_value, gap, folder), sensitivity


def sensitivity_sweep(sweep_param, min_val, max_val, n_rows, n_cols,
                      sens_param, base_value, gap, base_config, on_iteration=None):
    """The sensitivity to `sens_param` across a sweep of `sweep_param`; returns senssweep_grid.png's path."""
    folder = mode_folder(base_config, f"senssweep_{sweep_param}")
    values = np.linspace(min_val, max_val, n_rows * n_cols)
    cells = [([(sweep_param, value)], folder / f"cell_{k:03d}") for k, value in enumerate(values, 1)]
    titles = [f"{sweep_param} = {value:.3g}" for value in values]
    images = _sensitivity_cells(cells, titles, sens_param, base_value, gap, base_config, on_iteration)
    path = save_grid(images, n_rows, n_cols, folder / "senssweep_grid.png", FIGURES, fontsize=8)
    print(f"Saved grid -> {path}")
    return path


def sensitivity_sweep_2d(row_param, row_min, row_max, n_rows,
                         col_param, col_min, col_max, n_cols,
                         sens_param, base_value, gap, base_config, on_iteration=None):
    """The sensitivity to `sens_param` across a two-parameter sweep; returns senssweep2d_grid.png's path."""
    folder = mode_folder(base_config, f"senssweep2d_{row_param}_vs_{col_param}")
    cells, titles = [], []
    for r, row_value in enumerate(np.linspace(row_min, row_max, n_rows)):
        for c, col_value in enumerate(np.linspace(col_min, col_max, n_cols)):
            cells.append(([(row_param, row_value), (col_param, col_value)], folder / f"cell_r{r + 1}_c{c + 1}"))
            titles.append(f"{row_param} = {row_value:.3g}\n{col_param} = {col_value:.3g}")
    images = _sensitivity_cells(cells, titles, sens_param, base_value, gap, base_config, on_iteration)
    path = save_grid(images, n_rows, n_cols, folder / "senssweep2d_grid.png", FIGURES, fontsize=7)
    print(f"Saved 2D grid -> {path}")
    return path


def _sensitivity_cells(cells, titles, sens_param, base_value, gap, base_config, on_iteration):
    """Run a sensitivity study per cell; return [(sensitivity.png, title)] in cell order."""
    images, start = [], time.perf_counter()
    for k, ((assignments, cell_folder), title) in enumerate(zip(cells, titles), 1):
        run, cell_base, cell_gap = base_config.with_output_dir(cell_folder), base_value, gap
        for path, value in assignments:
            if path == BASE_VALUE:
                cell_base = float(value)
            elif path == GAP:
                cell_gap = float(value)
            else:
                run = apply_param(run, path, value)
        label = "   ".join(f"{path} = {value:.3g}" for path, value in assignments)
        print(f"\n[{k}/{len(cells)}]  {label}  |  sens_base = {cell_base:.3g}   gap = {cell_gap:+.3g}")
        image, _ = sensitivity_field(sens_param, cell_base, cell_gap, run, on_iteration)
        images.append((image, title))
        print(f"[{k}/{len(cells)}] done — total {time.perf_counter() - start:.1f}s")
    return images


# ── Output ────────────────────────────────────────────────────────────────────

def _save_csv(sensitivity, param_key, base_value, gap, folder):
    """sensitivity.csv: five metadata rows, then the field (row 0 = image top, as in the PNG).

    Values are raw finite-difference sensitivities, in Δdensity / Δ(param_key).
    """
    sensitivity = projection(sensitivity)          # 3-D: the depth average
    path = folder / "sensitivity.csv"
    with open(path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["param_key", param_key])
        writer.writerow(["base_value", f"{base_value:.6g}"])
        writer.writerow(["gap", f"{gap:+.6g}"])
        writer.writerow(["max_abs", f"{float(np.max(np.abs(sensitivity))):.6g}"])
        writer.writerow(["nely_nelx", f"{sensitivity.shape[0]}x{sensitivity.shape[1]}"])
        for row in np.flipud(sensitivity):
            writer.writerow([f"{value:.6g}" for value in row])
    print(f"Saved sensitivity CSV  -> {path}")


def _save_figure(density_base, sensitivity, param_key, base_value, gap, folder):
    """The sensitivity over a faint image of the base design, with a colour bar; returns the PNG's path."""
    density_base, sensitivity = projection(density_base), projection(sensitivity)   # 3-D: depth averages
    max_abs = float(np.max(np.abs(sensitivity)))
    if max_abs < 1e-9:
        max_abs = 1.0
    cmap = plt.cm.bwr
    norm = TwoSlopeNorm(vcenter=0.0, vmin=-max_abs, vmax=max_abs)

    # The base design as a ghost: void white, solid only 10 % grey.
    background = np.flipud(1.0 - density_base * 0.10)
    overlay = cmap(norm(np.flipud(sensitivity)))
    material = np.flipud(np.clip(density_base * 2.0, 0.0, 1.0))
    strength = np.flipud(np.clip(np.abs(sensitivity) / max_abs * 3.0, 0.0, 1.0))
    overlay[..., 3] = material * strength * 0.75

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.imshow(background, cmap="gray", vmin=0, vmax=1, interpolation="nearest", aspect="equal")
    ax.imshow(overlay, interpolation="nearest", aspect="equal")
    ax.axis("off")
    ax.set_title(f"Sensitivity  ∂density/∂({param_key})   base = {base_value:.4g},   Δ = {gap:+.4g}",
                 fontsize=10)
    scale = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    scale.set_array([])
    colorbar = fig.colorbar(scale, ax=ax, fraction=0.020, pad=0.02)
    colorbar.set_label(f"Δdensity / Δ{param_key}", fontsize=8)
    colorbar.ax.tick_params(labelsize=7)
    ax.text(0.01, 0.01, f"range  [{-max_abs:.3g},  +{max_abs:.3g}]",
            transform=ax.transAxes, fontsize=7, va="bottom", color="#555")

    fig.tight_layout()
    path = folder / "sensitivity.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved sensitivity figure -> {path}")
    return path
