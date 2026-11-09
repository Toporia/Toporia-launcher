# toporia_library/problems/material_auxetic.py — Material: Auxetic (negative Poisson's ratio) (multiscale).
#
# A 2-D material that widens when stretched: a periodic cell with the objective of Xia &
# Breitkopf, C12 − βⁿ (C11 + C22), whose stiffness term keeps the cell from going soft early
# and then fades, so C12 and the Poisson's ratio turn negative.  Measured: ν ≈ −0.74 with C11 ≈
# 0.07 after 300 iterations.  The homogenised matrix is written as a material card at the end.

from toporia_core.framework import Solver

from . import _material_presets as m

NAME = "Material: Auxetic (Negative Poisson's Ratio)"
ORDER = 37
ABOUT = ("A 2-D material with a negative Poisson's ratio (it widens when stretched), designed on a periodic cell"
         " at 35 % density.")
REFERENCE = ('L. Xia, P. Breitkopf, "Design of materials using topology optimization and energy-based homogenization'
             ' approach in Matlab", Struct. Multidisc. Optim. 52 (2015) 1229-1241 (the auxetic objective).'
             " Papers: https://doi.org/10.1007/s00158-015-1294-0")


def scenario():
    """The unit cell and the auxetic objective."""
    return m.cell(50.0, 0.35, {"type": "auxetic", "beta": 0.8})


def solver():
    """MMA with a small move limit and a density filter, from a cell with a hole."""
    return Solver(method="q4_periodic+mma", method_params={"move": 0.05},
                  representation={"type": "element_density", "start": "hole"},
                  filter_specs=[{"type": "density", "rmin": 2.0}], m=1.0, max_iter=300, tol=0.0)


def output():
    """At the end: the material card."""
    return m.card()


def _description():
    return m.description(__import__(__name__, fromlist=["x"]),
                         "Each iteration forms C^H on the periodic cell and the objective C12 - 0.8^n (C11 + C22), "
                         "with exact gradients, and updates the densities by MMA.",
                         "The Poisson's ratio reaches about -0.74 while C11 stays about 0.07 of the solid's "
                         "(tests/plugins/test_homogenisation.py).")
