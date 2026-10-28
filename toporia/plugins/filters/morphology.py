# plugins/filters/morphology.py — MorphologyFilter (smooth erode, dilate, open, close)
#
# Sigmund's morphology-based black-and-white filters.  Where the density filter
# takes a weighted MEAN of the neighbourhood, these take a smooth MAXIMUM
# (dilate: a pixel turns solid when any neighbour is solid) or a smooth MINIMUM
# (erode: a pixel stays solid only when all neighbours are).  Chaining the two
# gives the classical image-processing operators:
#
#   open  = dilate ∘ erode    removes solid features thinner than the radius
#   close = erode ∘ dilate    fills voids thinner than the radius
#
# so one filter, with a `mode`, covers all four; open/close are just two
# passes of the same machinery, which is why they are not separate classes.
#
# Neighbourhood: the cone weights H_ij = max(0, rmin − dist(i, j)) of the density
# filter (_neighbours.py), normalised by their row sums Hs_i.  With normalised
# weights a constant field maps to itself in every mode.
#
# Forward (Sigmund 2007, exponential-type smooth max/min):
#
#   dilate:  ρ̃_i =  1 + (1/β) · ln( Σ_j H_ij e^{ β(ρ_j − 1)} / Hs_i )
#   erode:   ρ̃_i =    − (1/β) · ln( Σ_j H_ij e^{−β ρ_j}      / Hs_i )
#
# (the "+1" and the e^{β(ρ−1)} are the usual log-sum-exp shift: the same value,
# but nothing overflows at large β).  β is the sharpness: small β is close to
# the weighted mean (a plain density filter), large β approaches the hard
# max/min.  The smooth operators bracket the weighted mean, erode ≤ mean ≤ dilate,
# by Jensen's inequality, but erode ≤ input ≤ dilate need not hold pointwise.
#
# Backward (exact): with S_i the sum inside the logarithm and e_j the shifted
# exponential of ρ_j,
#
#   ∂ρ̃_i/∂ρ_j = H_ij · e_j / (Hs_i · S_i)
#   dx_j      = e_j · Σ_i H_ij · s_i / (Hs_i · S_i)
#
# for both erode and dilate (the sign of the exponent differs, the derivative
# of −ln S / β and ln S / β does not).  Open/close chain two such passes, the
# intermediate field being recomputed from x_in rather than cached.
#
# β is schedulable (a geometric schedule on "filters[k].beta" continues it);
# unlike Heaviside there is no built-in doubling, the schedule is the continuation.
#
# This does not reuse am.py's smooth min/max: that is a different construction
# (a p-norm over a one-sided stencil with an adjoint rolled row by row), and
# its code is inlined in the layer sweep; the exponential form here is a sparse
# matrix product and shares the neighbour weights with the density filter.
#
# Reference: O. Sigmund, "Morphology-based black and white filters for topology
#   optimization", Struct. Multidisc. Optim. 33 (2007) 401-424,
#   DOI 10.1007/s00158-006-0087-x.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.filter import Filter
from toporia.plugins.shared_params import RMIN

from ._neighbours import neighbour_matrix

_MODES = ("erode", "dilate", "open", "close")


class MorphologyFilter(Filter):
    """Smooth erode / dilate / open / close over a cone neighbourhood (Sigmund 2007).

    rmin : neighbourhood radius in elements (as for the density filter).
    beta : sharpness of the smooth min/max; larger is closer to a hard min/max.
    mode : "erode", "dilate", "open" (erode then dilate) or "close" (dilate then erode).
    """

    name = "morphology"
    reference = (
        'O. Sigmund, "Morphology-based black and white filters for topology optimization", '
        'Struct. Multidisc. Optim. 33 (2007) 401-424.'
        ' Papers: https://doi.org/10.1007/s00158-006-0087-x'
    )
    label = "Morphology filter (erode / dilate / open / close)"
    use_when = (
        "To impose a minimum size on solid (open) or on holes (close), or to build eroded/dilated "
        "variants for a robust design. Works best with a continuation of its sharpness, like Heaviside."
    )
    dims = (2, 3)
    order = 35
    params = (
        RMIN,
        Param("beta", 8.0, "beta",
              "Sharpness of the smooth minimum / maximum. Small is close to a plain average, large to a hard min/max.",
              min=0.5, max=512.0, step=1.0, decimals=1),
        Param("mode", "open", "Operation",
              "Erode shrinks solid, dilate grows it. Open (erode then dilate) removes thin members; "
              "close (dilate then erode) fills thin gaps.",
              choices=(("erode", "Erode"), ("dilate", "Dilate"),
                       ("open", "Open (erode, then dilate)"), ("close", "Close (dilate, then erode)"))),
    )

    schedulable = ("beta",)

    def __init__(self, rmin=1.5, beta=8.0, mode="open"):
        if mode not in _MODES:
            raise ValueError(f"mode must be one of {', '.join(_MODES)}, got {mode!r}")
        self.rmin, self.beta, self.mode = float(rmin), float(beta), mode

    def setup(self, problem, solver):
        shape = problem.shape if getattr(problem, "dims", 2) == 3 else (problem.nely, problem.nelx)
        self._shape = tuple(shape)
        self.H, self.Hs = neighbour_matrix(self._shape, self.rmin)

    def set_parameter(self, name, value):
        """Change beta during a run (a schedule calls this)."""
        setattr(self, name, float(value))

    # --- one smooth pass -------------------------------------------------
    def _apply(self, x, op):
        """(result, e, S) of one pass: e = the shifted exponential of x, S = the weighted sum in the log."""
        b = self.beta
        flat = x.reshape(-1)
        e = np.exp(b * (flat - 1.0)) if op == "dilate" else np.exp(-b * flat)
        S = (self.H @ e) / self.Hs
        out = 1.0 + np.log(S) / b if op == "dilate" else -np.log(S) / b
        return out.reshape(self._shape), e, S

    def _pull_back(self, x, s, op):
        """The adjoint of one pass: d/dx given d/d(result)."""
        _, e, S = self._apply(x, op)
        return (e * (self.H.T @ (s.reshape(-1) / (self.Hs * S)))).reshape(self._shape)

    def _passes(self):
        """The ordered erode/dilate passes the mode stands for."""
        return {"erode": ("erode",), "dilate": ("dilate",),
                "open": ("erode", "dilate"), "close": ("dilate", "erode")}[self.mode]

    def forward(self, x):
        for op in self._passes():
            x = self._apply(x, op)[0]
        return x

    def backward(self, x_in, sensitivity):
        ops, fields = self._passes(), [x_in]
        for op in ops[:-1]:
            fields.append(self._apply(fields[-1], op)[0])
        for op, field in zip(reversed(ops), reversed(fields), strict=True):
            sensitivity = self._pull_back(field, sensitivity, op)
        return sensitivity
