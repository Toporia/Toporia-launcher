# toporia_library/problems/material_shear.py — Material: Maximum Shear Modulus (multiscale).
#
# The 2-D material that resists shear best at half density: a periodic cell maximising C33.
# The design is a material, not a part: see toporia_library/physics/homogenisation.py.  The
# homogenised matrix is written as a material card at the end (material.json).

from . import _material_presets as m

NAME = "Material: Maximum Shear Modulus"
ORDER = 36
ABOUT = ("The 2-D material that resists shear best at half density: a periodic cell maximising C33.")
REFERENCE = ("Inverse homogenisation: O. Sigmund, Int. J. Solids Struct. 31 (1994) 2313-2329; energy-based"
             " homogenisation: L. Xia, P. Breitkopf, Struct. Multidisc. Optim. 52 (2015) 1229-1241."
             " Papers: https://doi.org/10.1016/0020-7683(94)90154-6 https://doi.org/10.1007/s00158-015-1294-0")


def scenario():
    """The unit cell and its objective."""
    return m.cell(50.0, 0.5, {"type": "shear_modulus"}, depth=0.0)


def solver():
    """MMA, a density filter and a sharpening Heaviside projection, from a cell with a hole."""
    return m.projected_solver("q4_periodic", 2.0, 400)


def output():
    """At the end: the material card."""
    return m.card()


def _description():
    return m.description(__import__(__name__, fromlist=["x"]),
                         "Each iteration solves the three test strains on the periodic cell, forms C^H and the shear modulus C33 with its exact gradient, and updates the densities by MMA.",
                         "The shear modulus stays below the 2-D Hashin-Shtrikman upper bound for shear.")
