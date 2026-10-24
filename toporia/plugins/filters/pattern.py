# plugins/filters/pattern.py - PatternFilter (pattern repetition)
#
# Folds the domain into nx x ny (x nz) identical cells: all elements that sit
# at the same place inside their cell share one density, their mean.  Like
# symmetry.py and extrusion.py this is an average over a set of elements
# broadcast back, so it is linear and self-adjoint.
#
#     forward:   x_phys[c, i] = (1 / ncells) * sum_c' x[c', i]     (c = cell, i = place in the cell)
#     backward:  the same operation applied to the sensitivity
#
# With nx cells along x the element count nelx must be divisible by nx (and
# likewise y, z).  Toporia refuses a non-divisible mesh with an error naming
# the offending count rather than guessing a remainder: cells of unequal size
# are not identical, and silently dropping a strip of elements would change
# the problem.  Choose a mesh resolution (or Lx) that divides.
#
# Passive / void elements are not treated specially (as in symmetry.py): the
# model re-imposes them on the physical density afterwards.
#
# References: Bendsoe & Sigmund, Topology Optimization: Theory, Methods and
# Applications, Springer 2003 (pattern repetition as a design restriction);
# Almeida, Paulino & Silva, SMO 39 (2009) 359-371 (layout patterns).

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter


class PatternFilter(Filter):
    """Pattern repetition: nx x ny (x nz) identical cells, each the mean of all of them.

    nx, ny, nz : number of repetitions along each axis (nz only matters in 3-D and must be 1 in 2-D).
    """

    name = "pattern"
    reference = (
        'M. P. Bendsoe and O. Sigmund, Topology Optimization, Springer 2003; S. R. M. de '
        'Almeida, G. H. Paulino and E. C. N. Silva, Struct. Multidisc. Optim. 39 (2009) '
        '359-371.'
    )
    label = "Pattern repetition"
    order = 80
    dims = (2, 3)
    params = (
        Param("nx", 2, "Repeats in x", "Number of identical cells along x. The element count in x must be divisible by it.",
              min=1, max=64, step=1),
        Param("ny", 1, "Repeats in y", "Number of identical cells along y. The element count in y must be divisible by it.",
              min=1, max=64, step=1),
        Param("nz", 1, "Repeats in z", "Number of identical cells along z (3-D only). The element count in z must be divisible by it.",
              min=1, max=64, step=1),
    )

    def __init__(self, nx=2, ny=1, nz=1):
        self.reps = {"x": int(nx), "y": int(ny), "z": int(nz)}
        if min(self.reps.values()) < 1:
            raise ValueError(f"the number of repeats must be at least 1 - got nx={nx}, ny={ny}, nz={nz}")

    def setup(self, problem, solver):
        shape = tuple(problem.shape)
        names = ("y", "x") if len(shape) == 2 else ("z", "y", "x")
        if len(shape) == 2 and self.reps["z"] != 1:
            raise ValueError("nz > 1 needs a 3-D problem; leave nz = 1 in 2-D")
        for name, count in zip(names, shape, strict=True):
            if count % self.reps[name]:
                raise ValueError(
                    f"pattern repetition needs the element count to divide evenly into cells: "
                    f"{count} elements along {name} cannot be split into {self.reps[name]} identical cells"
                )
        self._names = names

    def forward(self, x):
        # Reshape each axis n into (reps, n/reps); averaging over the "reps" axes
        # is the fold, and broadcasting back is the repetition.
        split, fold = [], []
        for k, (name, count) in enumerate(zip(self._names, x.shape, strict=True)):
            r = self.reps[name]
            split += [r, count // r]
            fold.append(2 * k)
        cells = x.reshape(split)
        return np.broadcast_to(cells.mean(axis=tuple(fold), keepdims=True), cells.shape).reshape(x.shape).copy()

    def backward(self, x_in, sensitivity):
        # Averaging over cells is a symmetric projector: its adjoint is itself.
        return self.forward(sensitivity)
