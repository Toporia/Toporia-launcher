# toporia_library/models/q4_anisotropic.py — a part made of a designed material, as a model (multiscale).
#
# The macro half of two-scale design: plane stress in a material given by its constitutive
# matrix (toporia_library/physics/q4_anisotropic.py), typically the homogenised matrix of a unit
# cell designed with q4_periodic (the post-processor material_card writes the numbers).

from toporia_library.physics.q4_anisotropic import Q4Anisotropic

from .assembled import AssembledModel


class Q4AnisotropicModel(AssembledModel):
    """A 2-D part in a material of your own constitutive matrix, e.g. a designed microstructure."""

    name = "q4_anisotropic"
    label = "2-D Q4 in a designed material"
    use_when = ("To design a part made of a material you designed on a unit cell: paste its homogenised matrix "
                "(the material card) into C11 … C33.")
    reference = ('J. Wu, O. Sigmund, J. P. Groen, "Topology optimization of multi-scale structures: a review",'
                 " Struct. Multidisc. Optim. 63 (2021) 1455-1480. Papers: https://doi.org/10.1007/s00158-021-02881-8")
    order = 19
    physics = Q4Anisotropic
