# plugins/postprocessors/grey_level.py — how grey the design is, at the end and over the run.
#
# Sigmund's measure of non-discreteness, M_nd = 4/n Σ ρ(1 − ρ) × 100 %: 0 for
# a black-and-white design, 100 for a uniformly half-dense one.  It says how
# far a design is from something that can be made, and how much a threshold
# will change it.  Plotted over the iterations it also shows when a method
# (or a projection continuation) drives the design to black and white, which
# the end value alone hides.
#
# The final value is taken from the final physical density.  The per-iteration
# values come from the run's history (Result.history, filled by the
# optimisation loop); a design loaded from a saved folder has none, so then
# only the final value is given and no plot is written.  Holes and solid rings
# count like any other element: they are 0 or 1, so they add nothing.
#
# Reference: O. Sigmund, "Morphology-based black and white filters for
# topology optimization", Struct. Multidisc. Optim. 33 (2007) 401–424.

import csv

import matplotlib.pyplot as plt
import numpy as np

from toporia.framework.parts.postprocess import PostProcessor

from ._measure import grey_level


class GreyLevel(PostProcessor):
    """The measure of non-discreteness M_nd in percent, final and over the iterations."""

    name = "grey_level"
    reference = (
        'The measure of non-discreteness of O. Sigmund, "Morphology-based black and white '
        'filters for topology optimization", Struct. Multidisc. Optim. 33 (2007) 401-424.'
        ' Papers: https://doi.org/10.1007/s00158-006-0087-x'
    )
    label = "Grey level (M_nd) over the run"
    use_when = "To compare methods on how black-and-white their results are."
    order = 20
    table_metrics = ("final_pct", "peak_pct")
    dims = (2, 3)
    params = ()

    def process(self, result):
        final = 100.0 * grey_level(np.asarray(result.density, dtype=float))
        series = (result.history or {}).get("grey_level") or []
        if not series:                       # a saved run keeps no per-iteration densities
            return {"final_pct": final, "first_pct": None, "peak_pct": None, "iterations": None}
        values = 100.0 * np.asarray(series, dtype=float)
        with open(result.file("grey_level.csv"), "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["iteration", "M_nd_percent"])
            writer.writerows((i + 1, f"{v:.6g}") for i, v in enumerate(values))
        figure, axes = plt.subplots(figsize=(6, 3.5))
        axes.plot(np.arange(1, len(values) + 1), values)
        axes.set_xlabel("Iteration")
        axes.set_ylabel("M_nd (%)")
        axes.set_ylim(bottom=0.0)
        axes.grid(alpha=0.3)
        figure.tight_layout()
        figure.savefig(result.file("grey_level.png"), dpi=160)
        plt.close(figure)                    # no interactive window
        return {"final_pct": final, "first_pct": float(values[0]), "peak_pct": float(values.max()),
                "iterations": len(values)}
