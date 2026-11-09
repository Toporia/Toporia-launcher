# toporia_library/problems/cantilever_designed_material.py — a cantilever built of a designed material (two scales).
#
# The second step of two-scale design: the cantilever's scenario in the material designed by
# "Material: Maximum Bulk Modulus" (a square lattice at half density, 98 % of the
# Hashin–Shtrikman bulk bound).  Its homogenised matrix, from that preset's material card,
#
#     C11 = 0.3208,  C22 = 0.3208,  C12 = 0.0431,  C33 = 0.0126   (C13 = C23 ≈ 0)
#
# is stiff along the axes and weak in shear, so the optimiser lays the cantilever out in
# members along x and y instead of the usual ±45° truss: the layout follows the material's
# own stiff directions.  The q4_anisotropic model (toporia_library/physics/q4_anisotropic.py)
# scales that matrix by the material law, so the part is made of the lattice where solid.

from toporia_core.framework import Solver

from . import cantilever

NAME = "Cantilever of a Designed Material"
ORDER = 39
ABOUT = ("The cantilever built of a material designed on a unit cell (the maximum-bulk-modulus lattice): the layout"
         " follows the material's stiff directions.")
REFERENCE = ('Two-scale (sequential) design: J. Wu, O. Sigmund, J. P. Groen, "Topology optimization of multi-scale'
             ' structures: a review", Struct. Multidisc. Optim. 63 (2021) 1455-1480. Material from the preset'
             " Material: Maximum Bulk Modulus. Papers: https://doi.org/10.1007/s00158-021-02881-8")

#: The homogenised matrix of the maximum-bulk-modulus lattice (its material card, rounded).
LATTICE = {"C11": 0.3208, "C12": 0.0431, "C22": 0.3208, "C33": 0.0126, "C13": 0.0, "C23": 0.0}


def scenario():
    """The cantilever's physical problem, unchanged."""
    return cantilever.scenario()


def solver() -> Solver:
    """The designed material's matrix in the anisotropic Q4 model, a density filter and OC."""
    return Solver(method="q4_anisotropic+oc", method_params=dict(LATTICE),
                  filter_specs=[{"type": "density"}], m=1.0, max_iter=200, tol=0.01)
