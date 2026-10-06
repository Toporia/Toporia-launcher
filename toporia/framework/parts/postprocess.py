# framework/parts/postprocess.py — what is made of a finished design.
#
# An optimisation ends with a density field.  What is reported, compared and
# manufactured is made from it afterwards: a black-and-white design at the
# same volume and its compliance, a check that the structure is connected, the
# thinnest member, an outline for a laser cutter, a solid for a printer.  A
# PostProcessor does one such thing.  The run's Output section lists the ones
# to apply, in order, each switched on by being in the list:
#
#     output.postprocess = [{"type": "threshold"}, {"type": "connectivity"},
#                           {"type": "export_dxf"}]
#
# Each receives a Result — the final design, the meshed problem, the run, and
# the folder for its files — and returns numbers (metrics).  The engine prints
# them, writes them to run.json under "postprocess", and Compare Methods adds
# them to its table as columns ("threshold.compliance"), the same for every
# method.  `toporia post <run folder>` applies post-processors to a saved run
# without optimising again.
#
# Post-processors never change the optimisation: they live in the Output
# section, beside where the results go, not in the Solver.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Result:
    """A finished design, as every post-processor sees it.

    density   the final physical density, (nely, nelx), row 0 at y = 0
    problem   the meshed problem (framework/problem/mesh.py): element size,
              bounds, supports and loads
    run       the Run that produced it
    folder    where post-processors write their files (<run folder>/post)
    geometry  explicit outlines from the design representation, when it has
              them (moving morphable components: one closed polygon per bar,
              in mm); None for a density design
    """
    density: np.ndarray
    problem: object
    run: object
    folder: Path
    geometry: list | None = None
    #: The black-and-white design, once a post-processor (threshold) has made one.
    binary: np.ndarray | None = None
    #: The level the black-and-white design was cut at (0.5 until a threshold says otherwise).
    level: float = 0.5
    #: Every file written through file(), in order.
    files: list = field(default_factory=list)

    def solid(self):
        """The black-and-white design: the threshold's when one ran, else density ≥ 0.5, holes kept."""
        if self.binary is not None:
            return self.binary.astype(bool)
        problem = self.problem
        return np.clip((self.density >= 0.5).astype(float), problem.lower_bound, problem.upper_bound) >= 0.5

    def file(self, name):
        """The path to write a file called `name` to; the file is recorded with the result."""
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / name
        self.files.append(path)
        return path


class PostProcessor(ABC):
    """Something made of a finished design: numbers (metrics), and usually files."""

    #: Registry key used in output.postprocess specs: {"type": name, ...}.  Empty = abstract.
    name = ""
    #: Human-readable name for menus.
    label = ""
    #: Menu position; lower comes first.
    order = 100
    #: Tunable parameters (framework.params.Param).  The constructor must accept
    #: each one as a keyword argument of the same name.
    params = ()
    #: Optional packages it needs (see framework/registry.py).
    dependencies = ()
    #: The metrics worth a column when methods are compared; None means all of them.
    table_metrics = None

    @abstractmethod
    def process(self, result):
        """Do the work on `result` (a Result); return {metric name: number, bool or None}.

        Write files through result.file(name).  A metric that does not apply is
        None rather than left out, so a comparison table keeps its columns.
        """
