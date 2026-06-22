# SensitivitySweep.py — sweep over any parameter while computing a sensitivity field
#
# Combines the sweep and sensitivity ideas:
#   • For each cell in the sweep grid, run the two-pass sensitivity analysis.
#   • Assemble the resulting sensitivity images into one summary grid PNG.
#
# The sweep parameter can be ANY regular config field (volfrac, m, …) OR one of
# the two sensitivity-specific specials:
#   "sens.base_value"  — vary the nominal parameter value of the sensitivity run
#   "sens.gap"         — vary the finite-difference step size
#
# Two public functions mirror the 1-D / 2-D split used in sweep.py / sweep_2d.py:
#   sensitivity_sweep(...)        — vary one parameter over an n_rows × n_cols grid
#   sensitivity_sweep_2d(...)     — vary two parameters simultaneously


import time
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np

from toporia.core.config import TopOptConfig, LoadCase, apply_param
from toporia.functions.Sensitivity import sensitivity_field as _sensitivity_field


# ── 1-D sensitivity sweep ─────────────────────────────────────────────────────

def sensitivity_sweep(sweep_param, min_val, max_val, n_rows, n_cols,
                      sens_param, base_value, gap, base_config, on_iteration=None):
    """Run a 1-D sensitivity sweep.

    Parameters
    ----------
    sweep_param  : str   — parameter to vary across the grid
                           (any config field, "sens.base_value", or "sens.gap")
    min_val      : float — sweep range lower bound
    max_val      : float — sweep range upper bound
    n_rows/n_cols: int   — grid dimensions (total cells = n_rows × n_cols)
    sens_param   : str   — parameter for which to compute ∂density/∂param
    base_value   : float — nominal value for the sensitivity analysis
    gap          : float — finite-difference step size
    base_config  : TopOptConfig
    on_iteration : callable, optional
    """
    values     = np.linspace(min_val, max_val, n_rows * n_cols)
    output_dir = Path(base_config.output_dir) / f"senssweep_{sweep_param}"
    output_dir.mkdir(parents=True, exist_ok=True)

    img_paths, t0 = [], time.perf_counter()

    for k, value in enumerate(values, 1):
        cfg, eff_base, eff_gap = _apply_one(
            base_config, base_value, gap, sweep_param, value,
            cell_dir=output_dir / f"cell_{k:03d}",
        )
        print(f"\n[{k}/{len(values)}]  {sweep_param} = {value:.3g}"
              f"  |  sens_base = {eff_base:.3g}   gap = {eff_gap:+.3g}")
        img_path, _ = _sensitivity_field(sens_param, eff_base, eff_gap, cfg, on_iteration)
        img_paths.append((img_path, value))
        print(f"[{k}/{len(values)}] done — total {time.perf_counter() - t0:.1f}s")

    return _assemble_1d(img_paths, sweep_param, n_rows, n_cols, output_dir)


# ── 2-D sensitivity sweep ─────────────────────────────────────────────────────

def sensitivity_sweep_2d(row_param, row_min, row_max, n_rows,
                          col_param, col_min, col_max, n_cols,
                          sens_param, base_value, gap, base_config, on_iteration=None):
    """Run a 2-D sensitivity sweep varying two parameters simultaneously.

    Row parameter varies across rows; column parameter varies across columns.
    Both can be regular config fields or the sensitivity specials.
    """
    row_vals   = np.linspace(row_min, row_max, n_rows)
    col_vals   = np.linspace(col_min, col_max, n_cols)
    output_dir = (Path(base_config.output_dir)
                  / f"senssweep2d_{row_param}_vs_{col_param}")
    output_dir.mkdir(parents=True, exist_ok=True)

    total = n_rows * n_cols
    t0    = time.perf_counter()
    paths = np.empty((n_rows, n_cols), dtype=object)

    for r, rv in enumerate(row_vals):
        for c, cv in enumerate(col_vals):
            k = r * n_cols + c + 1
            cfg, eff_base, eff_gap = _apply_two(
                base_config, base_value, gap,
                row_param, rv, col_param, cv,
                cell_dir=output_dir / f"cell_r{r + 1}_c{c + 1}",
            )
            print(f"\n[{k}/{total}]  {row_param} = {rv:.3g}   {col_param} = {cv:.3g}"
                  f"  |  sens_base = {eff_base:.3g}   gap = {eff_gap:+.3g}")
            img_path, _ = _sensitivity_field(sens_param, eff_base, eff_gap, cfg, on_iteration)
            paths[r, c] = img_path
            print(f"[{k}/{total}] done — total {time.perf_counter() - t0:.1f}s")

    return _assemble_2d(paths, row_vals, col_vals, row_param, col_param, output_dir)


# ── Private helpers ────────────────────────────────────────────────────────────

def _apply_one(base_config, base_value, gap, param, value, cell_dir):
    """Return (cfg, effective_base, effective_gap) after applying one sweep value."""
    cfg = replace(base_config, output_dir=cell_dir)
    if param == "sens.base_value":
        return cfg, float(value), gap
    if param == "sens.gap":
        return cfg, base_value, float(value)
    return apply_param(cfg, param, value), base_value, gap


def _apply_two(base_config, base_value, gap, param_a, val_a, param_b, val_b, cell_dir):
    """Return (cfg, effective_base, effective_gap) after applying two sweep values."""
    cfg = replace(base_config, output_dir=cell_dir)
    eff_base, eff_gap = base_value, gap
    for param, val in [(param_a, val_a), (param_b, val_b)]:
        if param == "sens.base_value":
            eff_base = float(val)
        elif param == "sens.gap":
            eff_gap = float(val)
        else:
            cfg = apply_param(cfg, param, val)
    return cfg, eff_base, eff_gap


def _assemble_1d(img_paths, sweep_param, n_rows, n_cols, output_dir):
    sample   = mpimg.imread(str(img_paths[0][0]))
    ih, iw   = sample.shape[:2]
    cell_w   = max(4.0, iw / 120)
    cell_h   = max(2.5, ih / 120)
    fig, axes = plt.subplots(n_rows, n_cols, squeeze=False,
                             figsize=(cell_w * n_cols, cell_h * n_rows))
    for ax, (img_path, value) in zip(axes.flat, img_paths):
        ax.imshow(mpimg.imread(str(img_path)), aspect="auto")
        ax.set_title(f"{sweep_param} = {value:.3g}", fontsize=8)
        ax.axis("off")
    fig.tight_layout()
    grid_path = output_dir / "senssweep_grid.png"
    fig.savefig(grid_path, dpi=150)
    plt.close(fig)
    print(f"Saved grid → {grid_path}")
    return grid_path


def _assemble_2d(paths, row_vals, col_vals, row_param, col_param, output_dir):
    sample    = mpimg.imread(str(paths[0, 0]))
    ih, iw    = sample.shape[:2]
    cell_w    = max(4.0, iw / 120)
    cell_h    = max(2.5, ih / 120)
    n_rows, n_cols = paths.shape
    fig, axes = plt.subplots(n_rows, n_cols, squeeze=False,
                             figsize=(cell_w * n_cols, cell_h * n_rows))
    for r in range(n_rows):
        for c in range(n_cols):
            ax = axes[r, c]
            ax.imshow(mpimg.imread(str(paths[r, c])), aspect="auto")
            ax.set_title(
                f"{row_param} = {row_vals[r]:.3g}\n{col_param} = {col_vals[c]:.3g}",
                fontsize=7,
            )
            ax.axis("off")
    fig.tight_layout()
    grid_path = output_dir / "senssweep2d_grid.png"
    fig.savefig(grid_path, dpi=150)
    plt.close(fig)
    print(f"Saved 2D grid → {grid_path}")
    return grid_path


if __name__ == "__main__":
    BASE = TopOptConfig(
        m=0.5, volfrac=0.30, penal=3, rmin=1.5,
        filter_specs=[{"type": "density"}], max_iter=50, tol=0.05,
        load_cases=[LoadCase(Fmag=1.0, Fa=0.0, weight=0.5),
                    LoadCase(Fmag=1.0, Fa=270.0, weight=0.5)],
        save_every=0,
    )
    # Example: sweep volfrac from 0.20 to 0.40 in a 1×3 grid, sensitivity of volfrac at gap=0.05
    sensitivity_sweep("volfrac", 0.20, 0.40, 1, 3,
                      sens_param="volfrac", base_value=0.30, gap=0.05,
                      base_config=BASE)
