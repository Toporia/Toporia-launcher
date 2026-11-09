# toporia_library/problems/material_bulk_3d.py — Material: Maximum Bulk Modulus 3D (multiscale).
#
# The stiffest 3-D material under uniform expansion at 30 % density: a periodic cube whose bulk modulus approaches the 3-D Hashin-Shtrikman upper bound.
# The design is a material, not a part: see toporia_library/physics/homogenisation.py.  The
# homogenised matrix is written as a material card at the end (material.json).

from . import _material_presets as m

NAME = "Material: Maximum Bulk Modulus 3D"
ORDER = 38
ABOUT = ("The stiffest 3-D material under uniform expansion at 30 % density: a periodic cube whose bulk modulus approaches the 3-D Hashin-Shtrikman upper bound.")
REFERENCE = ("Inverse homogenisation: O. Sigmund, Int. J. Solids Struct. 31 (1994) 2313-2329; energy-based"
             " homogenisation: L. Xia, P. Breitkopf, Struct. Multidisc. Optim. 52 (2015) 1229-1241."
             " Papers: https://doi.org/10.1016/0020-7683(94)90154-6 https://doi.org/10.1007/s00158-015-1294-0")


def scenario():
    """The unit cell and its objective."""
    return m.cell(16.0, 0.3, {"type": "bulk_modulus"}, depth=16.0)


def solver():
    """MMA, a density filter and a sharpening Heaviside projection, from a cell with a hole."""
    return m.projected_solver("h8_periodic", 1.5, 220, every=40, end=16.0)


def output():
    """At the end: the material card."""
    return m.card()


def _description():
    return m.description(__import__(__name__, fromlist=["x"]),
                         "Each iteration solves the six test strains on the periodic cube, forms the 6 x 6 C^H and the bulk modulus with its exact gradient, and updates the densities by MMA.",
                         "The bulk modulus is compared with the 3-D Hashin-Shtrikman upper bound (tests/plugins/test_homogenisation.py).")
