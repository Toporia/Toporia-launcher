# compare_core.py — shared engine for all comparison analysis modes
#
# Imported by Compare_Two.py and CompareLoadCases.py.
# Not intended to be called directly — use compare_two() or compare_load_cases().
#
# Responsibilities:
#   • Define the three maximally-distinct hue constants used in both modes
#   • compare_core()     — run two pre-built configs, save the figure, return paths
#   • _save_comparison() — build the three-panel comparison image from two density arrays


import colorsys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

from toporia.engine.runner import run_single as _run_single

# ── Colour constants ──────────────────────────────────────────────────────────
# Three hues 120° apart on the colour wheel — maximally distinct from each other.
# Exported so callers can reference them for legends or documentation.
COLOR_A, COLOR_B, COLOR_BOTH = [
    np.array(colorsys.hsv_to_rgb(h / 360, 0.90, 0.95))
    for h in (30, 150, 270)
]   # orange · spring-green · blue-violet


# ── Core engine ───────────────────────────────────────────────────────────────

def compare_core(cfg_a, cfg_b, label_a, label_b, output_dir, on_iteration=None):
    """Run two optimisations then save the comparison figure.

    Parameters
    ----------
    cfg_a, cfg_b  : Run — fully configured, each with their own output_dir
    label_a/b     : str          — human-readable description shown in the figure
    output_dir    : Path         — where comparison.png is written
    on_iteration  : callable, optional — GUI callback(density, objectives, iteration)

    Returns
    -------
    (img_path, density_a ndarray, density_b ndarray)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    densities = []
    for label, label_text, cfg in [("A", label_a, cfg_a), ("B", label_b, cfg_b)]:
        print(f"\n=== Run {label}: {label_text} ===")
        densities.append(_run_single(cfg, on_iteration))

    density_a, density_b = densities
    img_path = _save_comparison(density_a, density_b, label_a, label_b, output_dir)
    return img_path, density_a, density_b


# ── Figure generation ─────────────────────────────────────────────────────────

def _save_comparison(density_a, density_b, label_a, label_b, output_dir):
    """Build and save the three-panel comparison figure.

    No threshold is applied.  Colour and brightness are derived from raw densities:

      shared = min(A, B)     — density both designs agree on
      a_only = A − shared    — density exclusive to design A
      b_only = B − shared    — density exclusive to design B

    The weighted hue mixture is tinted from white (intensity=0) toward the
    mixed colour (intensity=1), where intensity = max(A, B).
    """
    shared    = np.minimum(density_a, density_b)
    a_only    = density_a - shared
    b_only    = density_b - shared
    intensity = np.maximum(density_a, density_b)

    safe_int = np.where(intensity < 1e-9, 1.0, intensity)
    w_a    = a_only / safe_int
    w_b    = b_only / safe_int
    w_both = shared / safe_int

    mixed = (  w_a[:, :, None]    * COLOR_A[None, None, :]
             + w_b[:, :, None]    * COLOR_B[None, None, :]
             + w_both[:, :, None] * COLOR_BOTH[None, None, :])

    rgb = np.clip(1.0 + intensity[:, :, None] * (mixed - 1.0), 0.0, 1.0)
    rgb = np.flipud(rgb)

    # ── Layout: comparison on top (2× height), A and B below ─────────────────
    fig = plt.figure(figsize=(10, 7))
    gs  = GridSpec(2, 2, figure=fig, height_ratios=[2, 1], hspace=0.30, wspace=0.05)

    ax_comp = fig.add_subplot(gs[0, :])
    ax_a    = fig.add_subplot(gs[1, 0])
    ax_b    = fig.add_subplot(gs[1, 1])

    ax_comp.imshow(rgb, interpolation="nearest", aspect="equal")
    ax_comp.set_title(f"Comparison:  {label_a}   vs   {label_b}", fontsize=10)
    ax_comp.axis("off")
    ax_comp.legend(
        handles=[
            mpatches.Patch(color=COLOR_A,    label=f"A only  —  {label_a}"),
            mpatches.Patch(color=COLOR_B,    label=f"B only  —  {label_b}"),
            mpatches.Patch(color=COLOR_BOTH, label="Both  (shared density)"),
        ],
        loc="lower center", fontsize=8, bbox_to_anchor=(0.5, -0.06), ncol=3, frameon=True,
    )

    ax_a.imshow(np.flipud(1.0 - density_a), cmap="gray", vmin=0, vmax=1,
                interpolation="nearest", aspect="equal")
    ax_a.set_title(f"Design A  —  {label_a}", fontsize=8)
    ax_a.axis("off")

    ax_b.imshow(np.flipud(1.0 - density_b), cmap="gray", vmin=0, vmax=1,
                interpolation="nearest", aspect="equal")
    ax_b.set_title(f"Design B  —  {label_b}", fontsize=8)
    ax_b.axis("off")

    out_path = output_dir / "comparison.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved comparison → {out_path}")
    return out_path
