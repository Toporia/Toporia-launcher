# toporia_library/problems/material_bulk.py — Material: Maximum Bulk Modulus (multiscale).
#
# The stiffest 2-D material under uniform expansion at half density: a periodic cell whose bulk modulus approaches the Hashin-Shtrikman upper bound.
# The design is a material, not a part: see toporia_library/physics/homogenisation.py.  The
# homogenised matrix is written as a material card at the end (material.json).

from . import _material_presets as m

NAME = "Material: Maximum Bulk Modulus"
ORDER = 35
ABOUT = ("The stiffest 2-D material under uniform expansion at half density: a periodic cell whose bulk modulus approaches the Hashin-Shtrikman upper bound.")
REFERENCE = ("Inverse homogenisation: O. Sigmund, Int. J. Solids Struct. 31 (1994) 2313-2329; energy-based"
             " homogenisation: L. Xia, P. Breitkopf, Struct. Multidisc. Optim. 52 (2015) 1229-1241."
             " Papers: https://doi.org/10.1016/0020-7683(94)90154-6 https://doi.org/10.1007/s00158-015-1294-0")


def scenario():
    """The unit cell and its objective."""
    return m.cell(50.0, 0.5, {"type": "bulk_modulus"}, depth=0.0)


def solver():
    """MMA, a density filter and a sharpening Heaviside projection, from a cell with a hole."""
    return m.projected_solver("q4_periodic", 2.0, 400)


def output():
    """At the end: the material card."""
    return m.card()


def _description():
    return m.description(__import__(__name__, fromlist=["x"]),
                         "Each iteration solves the three test strains on the periodic cell, forms C^H and the bulk modulus (C11 + C22 + 2 C12)/4 with its exact gradient, and updates the densities by MMA.",
                         "The bulk modulus reaches about 97 % of the 2-D Hashin-Shtrikman upper bound at volume fraction 0.5 (tests/plugins/test_homogenisation.py).")
