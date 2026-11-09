# toporia_library/responses/homogenised.py — what a material microstructure is worth (multiscale).
#
# On a periodic unit cell (toporia_library/physics/homogenisation.py) the physics gives the
# homogenised elasticity matrix C^H (Voigt; 3 × 3 in 2-D, 6 × 6 in 3-D) and ∂C^H_ij/∂ρ.  These
# responses make objectives of it, each a linear or rational function of C^H, so its gradient
# is the chain rule over ∂C^H_ij/∂ρ:
#
#   bulk_modulus     κ = (C11 + C22 + 2 C12) / 4                         (2-D)
#                    κ = (C11 + C22 + C33 + 2 (C12 + C13 + C23)) / 9     (3-D)
#                    maximised: the value is −κ / κ⁰ (κ⁰ at the start design)
#   shear_modulus    G = C33 (2-D),  G = (C44 + C55 + C66) / 3 (3-D)    maximised: −G / G⁰
#   auxetic          J = (C12 − βⁿ (C11 + C22)) / (C11⁰ + C22⁰),  n the iteration (Xia & Breitkopf):
#                    early the stiffness term keeps the cell from going soft, later C12 alone is
#                    pushed below zero, so the Poisson's ratio ν = C12 / ((C11 + C22)/2) turns
#                    negative: an auxetic material, which widens when stretched.  (Minimising ν
#                    itself does not work: a cell with almost no stiffness games the ratio.)
#
# The bulk-modulus optimum of a two-phase (solid/void) material at volume fraction f is bounded
# by the Hashin–Shtrikman upper bound; a good microstructure comes close to it.
#
# Reference: O. Sigmund, Int. J. Solids Struct. 31 (1994) 2313-2329 (inverse homogenisation);
# L. Xia, P. Breitkopf, "Design of materials using topology optimization and energy-based
# homogenization approach in Matlab", Struct. Multidisc. Optim. 52 (2015) 1229-1241.

import numpy as np

from toporia_core.framework.params import Param
from toporia_core.framework.parts.physics import HOMOGENISED
from toporia_core.framework.parts.response import OBJECTIVE_ROLE, Response, ResponseValue

REFERENCE = ("Inverse homogenisation: O. Sigmund, Int. J. Solids Struct. 31 (1994) 2313-2329; energy-based"
             " homogenisation in Matlab: L. Xia, P. Breitkopf, Struct. Multidisc. Optim. 52 (2015) 1229-1241."
             " Papers: https://doi.org/10.1016/0020-7683(94)90154-6 https://doi.org/10.1007/s00158-015-1294-0")


class _Homogenised(Response):
    """A function of the homogenised elasticity matrix, with its exact gradient."""

    roles = (OBJECTIVE_ROLE,)
    requires = (HOMOGENISED,)
    reference = REFERENCE
    #: Divide by the value at the start design (for maximised moduli, so the objective is O(1)).
    normalised = True

    def setup(self, physics, problem, settings):
        super().setup(physics, problem, settings)
        self._reference = None

    def _weights(self, C):
        """(value, W) with value = f(C) and W_ij = ∂f/∂C_ij."""
        raise NotImplementedError

    def _report(self, C):
        """Extra numbers worth recording."""
        return {}

    def evaluate(self, state, gradient=True):
        C = self.physics.homogenised(state)
        value, W = self._weights(C)
        reported = {f"C{i + 1}{j + 1}": float(C[i, j]) for i in range(len(C)) for j in range(i, len(C))}
        reported[self.name] = float(value)
        reported.update(self._report(C))
        scale, sign = 1.0, (-1.0 if self.maximise else 1.0)
        if self.normalised:
            if self._reference is None:
                self._reference = abs(value) if abs(value) > 1e-300 else 1.0
            scale = 1.0 / self._reference
        if not gradient:
            return ResponseValue(sign * scale * value, reported=reported)
        slope = np.zeros(state.density.shape)
        for i, j in zip(*np.nonzero(W), strict=True):
            slope += W[i, j] * self.physics.homogenised_slope(state, i, j)
        return ResponseValue(sign * scale * value, sign * scale * slope, reported=reported)


class BulkModulus(_Homogenised):
    """Maximise the effective bulk modulus of a periodic material."""

    name = "bulk_modulus"
    label = "Bulk modulus (maximise, unit cell)"
    use_when = "To design the stiffest material under uniform expansion or pressure, on a periodic unit cell."
    order = 70
    maximise = True

    def _weights(self, C):
        d = 2 if len(C) == 3 else 3
        W = np.zeros_like(C)
        W[:d, :d] = 1.0 / d ** 2
        return float(np.sum(C[:d, :d]) / d ** 2), W


class ShearModulus(_Homogenised):
    """Maximise the effective shear modulus of a periodic material."""

    name = "shear_modulus"
    label = "Shear modulus (maximise, unit cell)"
    use_when = "To design the material that resists shear best, on a periodic unit cell."
    order = 71
    maximise = True

    def _weights(self, C):
        W = np.zeros_like(C)
        if len(C) == 3:
            W[2, 2] = 1.0
            return float(C[2, 2]), W
        W[3, 3] = W[4, 4] = W[5, 5] = 1.0 / 3.0
        return float((C[3, 3] + C[4, 4] + C[5, 5]) / 3.0), W


class Auxetic(_Homogenised):
    """A negative Poisson's ratio (auxetic material), by Xia & Breitkopf's objective C12 − βⁿ (C11 + C22)."""

    name = "auxetic"
    label = "Negative Poisson's ratio (auxetic, unit cell)"
    use_when = ("To design an auxetic material, which widens when stretched, on a periodic unit cell. Use MMA; "
                "start from a cell with a hole.")
    order = 72
    maximise = False
    normalised = False
    params = (Param("beta", 0.8, "Stiffness weight decay", "β in C12 − βⁿ (C11 + C22): the weight that keeps the "
                    "cell stiff falls by this factor every iteration.", min=0.0, max=0.99, step=0.05, decimals=3),)

    def setup(self, physics, problem, settings):
        super().setup(physics, problem, settings)
        self.iteration, self._scale = 0, None

    def evaluate(self, state, gradient=True):
        if gradient:
            self.iteration += 1                     # one gradient evaluation per iteration
        return super().evaluate(state, gradient)

    def _weights(self, C):
        if self._scale is None:                     # O(1): divided by C11 + C22 at the start design
            self._scale = max(float(C[0, 0] + C[1, 1]), 1e-300)
        weight = self.settings["beta"] ** max(self.iteration, 1)
        W = np.zeros_like(C)
        W[0, 1] = W[1, 0] = 0.5 / self._scale
        W[0, 0] = W[1, 1] = -weight / self._scale
        return float((C[0, 1] - weight * (C[0, 0] + C[1, 1])) / self._scale), W

    def _report(self, C):
        return {"poisson_ratio": float(C[0, 1] / (0.5 * (C[0, 0] + C[1, 1])))}
