# Compare_Two.py — compare two designs that differ in one scalar parameter
#
# Runs two optimisation passes with identical settings except for one parameter
# (e.g. volfrac=0.20 vs volfrac=0.40), then produces a colour-coded comparison
# figure showing what material is unique to each design and what is shared.
#
# Colour key  (hues 120° apart — maximally distinct):
#   orange       (HSV  30°) — material only in design A
#   spring-green (HSV 150°) — material only in design B
#   blue-violet  (HSV 270°) — material present in both designs
#   white                   — void in both designs
#
# Two ways to use:
#   1. python Compare_Two.py   → runs the example in __main__
#   2. from Compare_Two import compare_two


from pathlib import Path

from toporia.engine.modes.compare_core import COLOR_A, COLOR_B, COLOR_BOTH, compare_core  # noqa: F401
from toporia.framework import LoadCase, Run, apply_param

#   COLOR_* re-exported so existing  `from Compare_Two import _COLOR_A …`
#   imports keep working after the refactor.
_COLOR_A, _COLOR_B, _COLOR_BOTH = COLOR_A, COLOR_B, COLOR_BOTH


def compare_two(param_key, value_a, value_b, base_config, on_iteration=None):
    """Compare two designs that differ in exactly one scalar parameter.

    Parameters
    ----------
    param_key    : str   — parameter to vary (e.g. "volfrac", "lc0.Fmag")
    value_a      : float — parameter value for design A
    value_b      : float — parameter value for design B
    base_config  : Run — all other settings, shared between both runs
    on_iteration : callable, optional — GUI callback(density, objectives, iteration)

    Returns
    -------
    (Path to comparison PNG, density_a ndarray, density_b ndarray)
    """
    output_dir = (Path(base_config.output.dir)
                  / f"compare_{param_key}_{value_a:.4g}_vs_{value_b:.4g}")
    cfg_a = apply_param(
        base_config.with_output_dir(output_dir / "run_A"),
        param_key, value_a,
    )
    cfg_b = apply_param(
        base_config.with_output_dir(output_dir / "run_B"),
        param_key, value_b,
    )
    return compare_core(
        cfg_a, cfg_b,
        f"{param_key} = {value_a:.4g}",
        f"{param_key} = {value_b:.4g}",
        output_dir, on_iteration,
    )


if __name__ == "__main__":
    BASE = Run().updated(
        m=0.5, volfrac=0.25,
        filter_specs=[{"type": "density"}], max_iter=50, tol=0.05,
        load_cases=[LoadCase(Fmag=1.0, Fa=0.0,   weight=0.5),
                    LoadCase(Fmag=1.0, Fa=270.0, weight=0.5)],
        save_every=0,
    )
    compare_two("volfrac", 0.20, 0.40, BASE)
