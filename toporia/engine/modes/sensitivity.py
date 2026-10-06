# Sensitivity.py — finite-difference sensitivity field for one parameter
#
# Runs two optimisations: one at `base_value`, one at `base_value + gap`.
# The per-element sensitivity is:
#
#   sensitivity[i,j] = (density_perturbed[i,j] − density_base[i,j]) / gap
#
# Output: a single image showing the sensitivity overlaid on the base design.
#
#   Background layer  — base design in standard grayscale (solid = dark)
#   Overlay layer     — blue–white–red sensitivity, semi-transparent so the
#                       base design stays legible through the colours
#
#   red   → positive sensitivity  (more material when parameter increases)
#   white → near-zero sensitivity (element is insensitive)
#   blue  → negative sensitivity  (less material when parameter increases)
#
# Alpha strategy (keeps the base always visible):
#   α = material_presence × sensitivity_magnitude × 0.75
#   → elements with zero sensitivity show only the base design
#   → elements with high sensitivity are ≤75 % opaque, base still shows at ≥25 %
#
# Two ways to use:
#   1. python Sensitivity.py           → uses config in main()
#   2. from toporia.engine.modes.sensitivity import sensitivity_field  → call from GUI


import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

from toporia.engine.loop import run_single as _run_single
from toporia.framework import LoadCase, Run, apply_param


def sensitivity_field(param_key, base_value, gap, base_config, on_iteration=None):
    """Compute and visualise the per-element density sensitivity to one parameter.

    Parameters
    ----------
    param_key    : str   — parameter to perturb (e.g. "volfrac", "lc0.Fmag")
    base_value   : float — nominal parameter value
    gap          : float — finite-difference step (positive or negative)
    base_config  : Run — all other settings, shared between both runs
    on_iteration : callable, optional — GUI callback(density, objectives, iteration)

    Returns
    -------
    (Path to saved PNG, sensitivity ndarray  [nely × nelx])
    """
    output_dir = (Path(base_config.output.dir)
                  / f"sensitivity_{param_key}_{base_value:.4g}_d{gap:+.4g}")
    output_dir.mkdir(parents=True, exist_ok=True)

    densities = []
    for label, value in [("base", base_value), ("perturbed", base_value + gap)]:
        cfg = apply_param(
            base_config.with_output_dir(output_dir / f"run_{label}"),
            param_key, value,
        )
        print(f"\n=== Run {label}: {param_key} = {value:.4g} ===")
        density = _run_single(cfg, on_iteration)
        densities.append(density)

    density_base, density_pert = densities
    sens = (density_pert - density_base) / gap

    _save_csv(sens, param_key, base_value, gap, output_dir)
    img_path = _save_figure(density_base, sens, param_key, base_value, gap, output_dir)
    return img_path, sens


def _save_csv(sens, param_key, base_value, gap, output_dir):
    """Write sensitivity.csv — metadata header rows then the raw 2-D sensitivity array.

    Row ordering matches the PNG (row 0 = top of image, i.e. flipud applied).
    Values are the unscaled finite-difference sensitivities in units of
    Δdensity / Δ(param_key).
    """
    out = np.flipud(sens)   # row 0 = image top, consistent with the PNG
    csv_path = output_dir / "sensitivity.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["param_key",   param_key])
        w.writerow(["base_value",  f"{base_value:.6g}"])
        w.writerow(["gap",         f"{gap:+.6g}"])
        w.writerow(["max_abs",     f"{float(np.max(np.abs(sens))):.6g}"])
        w.writerow(["nely_nelx",   f"{sens.shape[0]}x{sens.shape[1]}"])
        for row in out:
            w.writerow([f"{v:.6g}" for v in row])
    print(f"Saved sensitivity CSV  → {csv_path}")


def _save_figure(density_base, sens, param_key, base_value, gap, output_dir):
    """Single-panel figure: sensitivity overlay on the base design."""
    max_abs = float(np.max(np.abs(sens)))
    if max_abs < 1e-9:
        max_abs = 1.0

    cmap = plt.cm.bwr
    norm = TwoSlopeNorm(vcenter=0.0, vmin=-max_abs, vmax=max_abs)

    # ── Background: base design as a very light ghost (solid ≈ 10 % gray) ─────
    # density 0 → white (1.0),  density 1 → near-white (0.90)
    # This keeps the structural shape readable without competing with the colours.
    bg = np.flipud(1.0 - density_base * 0.10)

    # ── Sensitivity overlay (RGBA) ─────────────────────────────────────────────
    sens_disp  = np.flipud(sens)
    sens_rgba  = cmap(norm(sens_disp))                  # shape (ny, nx, 4)

    # Alpha: proportional to material presence × sensitivity magnitude.
    # Zero-sensitivity elements are fully transparent — base design unchanged.
    # Maximum opacity is 0.75 so the base structure always shows through.
    material  = np.flipud(np.clip(density_base * 2.0, 0.0, 1.0))
    sens_str  = np.flipud(np.clip(np.abs(sens) / max_abs * 3.0, 0.0, 1.0))
    sens_rgba[..., 3] = material * sens_str * 0.75

    # ── Single-panel figure ────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(11, 5))

    ax.imshow(bg, cmap="gray", vmin=0, vmax=1,
              interpolation="nearest", aspect="equal")
    ax.imshow(sens_rgba, interpolation="nearest", aspect="equal")

    ax.axis("off")
    ax.set_title(
        f"Sensitivity  ∂density/∂({param_key})"
        f"   base = {base_value:.4g},   Δ = {gap:+.4g}",
        fontsize=10,
    )

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.020, pad=0.02)
    cbar.set_label(f"Δdensity / Δ{param_key}", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax.text(0.01, 0.01, f"range  [{-max_abs:.3g},  +{max_abs:.3g}]",
            transform=ax.transAxes, fontsize=7, va="bottom", color="#555")

    fig.tight_layout()
    out_path = output_dir / "sensitivity.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved sensitivity figure → {out_path}")
    return out_path


if __name__ == "__main__":
    BASE = Run().updated(
        m=0.5, volfrac=0.30,
        filter_specs=[{"type": "density"}], max_iter=50, tol=0.05,
        load_cases=[LoadCase(Fmag=1.0, Fa=0.0, weight=0.5),
                    LoadCase(Fmag=1.0, Fa=270.0, weight=0.5)],
        save_every=0,
    )
    sensitivity_field("volfrac", base_value=0.30, gap=0.05, base_config=BASE)
