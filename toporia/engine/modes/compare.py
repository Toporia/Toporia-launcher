# engine/modes/compare.py — two optimisations side by side, and what differs between them.
#
#   compare_two          the same run with one parameter at two values
#                        (e.g. volfrac 0.20 against 0.40)
#   compare_load_cases   the same run with two different sets of load cases
#   compare_runs         any two prepared Runs (used by both, and by `toporia compare`)
#
# The figure, comparison.png, shows the two designs and one overlay of them:
#
#   orange        material only in design A      (hue  30°)
#   spring green  material only in design B      (hue 150°)
#   blue violet   material in both               (hue 270°)
#   white         void in both
#
# The three hues are 120° apart on the colour wheel, as distinct as three
# colours can be.  No threshold is applied: colour and brightness follow the
# raw densities, so grey regions stay visibly grey.

import colorsys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

from toporia.engine.loop import run_single
from toporia.framework import apply_param

COLOR_A, COLOR_B, COLOR_BOTH = [np.array(colorsys.hsv_to_rgb(hue / 360, 0.90, 0.95)) for hue in (30, 150, 270)]


def compare_two(param_key, value_a, value_b, base_config, on_iteration=None):
    """Compare two designs that differ in one parameter path.

    Returns (path of comparison.png, density A, density B).
    """
    folder = Path(base_config.output.dir) / f"compare_{param_key}_{value_a:.4g}_vs_{value_b:.4g}"
    run_a = apply_param(base_config.with_output_dir(folder / "run_A"), param_key, value_a)
    run_b = apply_param(base_config.with_output_dir(folder / "run_B"), param_key, value_b)
    return compare_runs(run_a, run_b, f"{param_key} = {value_a:.4g}", f"{param_key} = {value_b:.4g}",
                        folder, on_iteration)


def compare_load_cases(load_cases_a, load_cases_b, base_config, on_iteration=None):
    """Compare two designs that differ only in their load cases (lists of LoadCase).

    Returns (path of comparison.png, density A, density B).
    """
    folder = (Path(base_config.output.dir)
              / f"compare_lc_{_load_case_tag(load_cases_a)}_vs_{_load_case_tag(load_cases_b)}")
    # List the load cases first, so the log is readable before the runs start.
    for label, load_cases in (("A", load_cases_a), ("B", load_cases_b)):
        print(f"  Run {label}: {len(load_cases)} load case(s)")
        for i, case in enumerate(load_cases):
            print(f"    LC{i + 1}:  Fmag={case.Fmag:.3g}  Fa={case.Fa:.1f}°  weight={case.weight:.3g}")

    run_a = apply_param(base_config.with_output_dir(folder / "run_A"), "load_cases", load_cases_a)
    run_b = apply_param(base_config.with_output_dir(folder / "run_B"), "load_cases", load_cases_b)
    return compare_runs(run_a, run_b, _load_case_label(load_cases_a), _load_case_label(load_cases_b),
                        folder, on_iteration)


def compare_runs(run_a, run_b, label_a, label_b, output_dir, on_iteration=None):
    """Run two prepared Runs (each with its own output folder) and draw comparison.png in `output_dir`.

    Returns (path of comparison.png, density A, density B).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    densities = []
    for name, label, run in (("A", label_a, run_a), ("B", label_b, run_b)):
        print(f"\n=== Run {name}: {label} ===")
        densities.append(run_single(run, on_iteration))
    density_a, density_b = densities
    return _save_figure(density_a, density_b, label_a, label_b, output_dir), density_a, density_b


# ── The figure ────────────────────────────────────────────────────────────────

def _overlay(density_a, density_b):
    """RGB image of two density fields, coloured by which design has the material.

    shared = min(A, B), a_only = A − shared, b_only = B − shared; the three
    colours are mixed in those proportions, then tinted from white towards
    the mix by intensity = max(A, B), so void stays white.
    """
    shared = np.minimum(density_a, density_b)
    intensity = np.maximum(density_a, density_b)
    safe = np.where(intensity < 1e-9, 1.0, intensity)       # avoid 0/0 where both are void
    mixed = ((density_a - shared)[:, :, None] / safe[:, :, None] * COLOR_A
             + (density_b - shared)[:, :, None] / safe[:, :, None] * COLOR_B
             + shared[:, :, None] / safe[:, :, None] * COLOR_BOTH)
    return np.flipud(np.clip(1.0 + intensity[:, :, None] * (mixed - 1.0), 0.0, 1.0))


def _save_figure(density_a, density_b, label_a, label_b, output_dir):
    """The overlay on top (twice the height), the two designs below; returns the PNG's path."""
    fig = plt.figure(figsize=(10, 7))
    grid = GridSpec(2, 2, figure=fig, height_ratios=[2, 1], hspace=0.30, wspace=0.05)
    ax_both, ax_a, ax_b = fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])

    ax_both.imshow(_overlay(density_a, density_b), interpolation="nearest", aspect="equal")
    ax_both.set_title(f"Comparison:  {label_a}   vs   {label_b}", fontsize=10)
    ax_both.axis("off")
    ax_both.legend(
        handles=[mpatches.Patch(color=COLOR_A, label=f"A only  —  {label_a}"),
                 mpatches.Patch(color=COLOR_B, label=f"B only  —  {label_b}"),
                 mpatches.Patch(color=COLOR_BOTH, label="Both  (shared density)")],
        loc="lower center", fontsize=8, bbox_to_anchor=(0.5, -0.06), ncol=3, frameon=True,
    )
    for ax, density, title in ((ax_a, density_a, f"Design A  —  {label_a}"),
                               (ax_b, density_b, f"Design B  —  {label_b}")):
        ax.imshow(np.flipud(1.0 - density), cmap="gray", vmin=0, vmax=1, interpolation="nearest", aspect="equal")
        ax.set_title(title, fontsize=8)
        ax.axis("off")

    path = output_dir / "comparison.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved comparison -> {path}")
    return path


def _load_case_tag(load_cases):
    """Short, folder-safe name for a list of load cases."""
    return f"{len(load_cases)}lc_" + "-".join(f"{case.Fa:.0f}d" for case in load_cases[:3])


def _load_case_label(load_cases):
    """One line describing a list of load cases, for titles and the legend."""
    return "  |  ".join(f"Fa={case.Fa:.0f}°  w={case.weight:.2f}" for case in load_cases)
