# CompareLoadCases.py — compare two designs that differ only in their load cases
#
# Runs two optimisation passes with identical mesh, material, and solver settings
# but completely independent load-case lists.  Produces the same colour-coded
# comparison figure as Compare_Two using the shared engine in compare_core.py.
#
# Colour key  (hues 120° apart — maximally distinct):
#   orange       (HSV  30°) — material only in design A
#   spring-green (HSV 150°) — material only in design B
#   blue-violet  (HSV 270°) — material present in both designs
#   white                   — void in both designs
#
# Two ways to use:
#   1. python CompareLoadCases.py   → runs the example in __main__
#   2. from CompareLoadCases import compare_load_cases


from dataclasses import replace
from pathlib import Path

from toporia.core.config import TopOptConfig, LoadCase
from toporia.functions.compare_core import compare_core


def compare_load_cases(load_cases_a, load_cases_b, base_config, on_iteration=None):
    """Compare two designs that differ only in their load-case sets.

    Parameters
    ----------
    load_cases_a : list[LoadCase] — load cases for design A
    load_cases_b : list[LoadCase] — load cases for design B
    base_config  : TopOptConfig  — all other settings (volfrac, mesh, …) shared
    on_iteration : callable, optional — GUI callback(density, objectives, iteration)

    Returns
    -------
    (Path to comparison PNG, density_a ndarray, density_b ndarray)
    """
    output_dir = (Path(base_config.output_dir)
                  / f"compare_lc_{_lc_tag(load_cases_a)}_vs_{_lc_tag(load_cases_b)}")

    # Print load-case breakdown upfront so the log is readable before runs start.
    for label, lcs in [("A", load_cases_a), ("B", load_cases_b)]:
        print(f"  Run {label}: {len(lcs)} load case(s)")
        for i, lc in enumerate(lcs):
            print(f"    LC{i + 1}:  Fmag={lc.Fmag:.3g}  Fa={lc.Fa:.1f}°  weight={lc.weight:.3g}")

    cfg_a = replace(base_config, load_cases=load_cases_a, output_dir=output_dir / "run_A")
    cfg_b = replace(base_config, load_cases=load_cases_b, output_dir=output_dir / "run_B")
    return compare_core(
        cfg_a, cfg_b,
        _lc_label(load_cases_a),
        _lc_label(load_cases_b),
        output_dir, on_iteration,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lc_tag(lcs):
    """Short directory-safe string for a load-case list (used in folder names)."""
    return f"{len(lcs)}lc_" + "-".join(f"{lc.Fa:.0f}d" for lc in lcs[:3])


def _lc_label(lcs):
    """One-line human-readable summary for figure titles and legend patches."""
    return "  |  ".join(f"Fa={lc.Fa:.0f}°  w={lc.weight:.2f}" for lc in lcs)


if __name__ == "__main__":
    BASE = TopOptConfig(
        m=0.5, volfrac=0.25, penal=3, rmin=1.5,
        filter_specs=[{"type": "density"}], max_iter=50, tol=0.05,
        save_every=0,
    )
    LCS_A = [LoadCase(Fmag=1.0, Fa=0.0, weight=1.0)]
    LCS_B = [LoadCase(Fmag=1.0, Fa=0.0,   weight=0.5),
             LoadCase(Fmag=1.0, Fa=270.0, weight=0.5)]
    compare_load_cases(LCS_A, LCS_B, BASE)
