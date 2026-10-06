# plugins/postprocessors/threshold.py — black and white at the same volume, and its compliance.
#
# Methods finish with different amounts of grey, and grey material counts
# partly as stiffness, so their own compliances are not comparable.  Papers
# therefore cut every design to black and white and analyse it again.  By
# default the cut keeps the volume: the free elements with the highest
# density become solid until the material of the original design is used,
# while holes and solid rings stay as they are.  The cut design is then
# analysed by the referee (Q4, SIMP p = 3, no filter), the same for every method.
#
# Later post-processors in the list (connectivity, feature size, exports) use
# this black-and-white design.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.postprocess import PostProcessor

from ._measure import grey_level, pinned, referee_compliance, save_image


class Threshold(PostProcessor):
    """Black and white at the original volume, analysed again by the referee."""

    name = "threshold"
    label = "Threshold to black and white"
    order = 10
    table_metrics = ("compliance", "increase_pct")
    params = (
        Param("keep_volume", True, "Keep the volume",
              "Cut where the black-and-white design uses the same material as the original. "
              "When off, cut at the fixed level below."),
        Param("level", 0.5, "Level", "Densities at or above it become solid, when the volume is not kept.",
              min=0.0, max=1.0, step=0.05, decimals=3),
    )

    def __init__(self, keep_volume=True, level=0.5):
        self.keep_volume, self.level = bool(keep_volume), float(level)

    def process(self, result):
        problem = result.problem
        density = np.clip(result.density, problem.lower_bound, problem.upper_bound)
        fixed = pinned(problem)
        binary = np.where(fixed, problem.lower_bound, 0.0)
        free = np.flatnonzero(~fixed.ravel())
        if self.keep_volume:
            # The k densest free elements, k chosen so the total material is unchanged.
            k = min(max(int(round(density.sum() - binary.sum())), 0), free.size)
            order = free[np.argsort(-density.ravel()[free], kind="stable")]
            binary.ravel()[order[:k]] = 1.0
            level = float(density.ravel()[order[k - 1]]) if k else 1.0
        else:
            level = self.level
            binary.ravel()[free] = (density.ravel()[free] >= level).astype(float)
        result.binary, result.level = binary, level

        grey = referee_compliance(problem, density)
        cut = referee_compliance(problem, binary)
        save_image(binary, result.file("thresholded.png"))
        np.savetxt(result.file("thresholded.csv"), np.flipud(binary), fmt="%d", delimiter=",")
        return {"level": level, "volume": float(binary.mean()), "grey_level_before": grey_level(density),
                "compliance": cut, "compliance_grey": grey, "increase_pct": 100.0 * (cut / grey - 1.0)}
