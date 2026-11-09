# toporia_library/models/h8_periodic.py — a 3-D periodic unit cell as a model (multiscale).
#
# The 3-D counterpart of q4_periodic.py: H8 bricks, six unit test strains, a 6 × 6 homogenised
# elasticity matrix (toporia_library/physics/homogenisation.py).  Needs a scenario with a depth.

from toporia_library.physics.homogenisation import H8PeriodicCell

from .assembled import AssembledModel


class H8PeriodicModel(AssembledModel):
    """A 3-D periodic unit cell: design a material microstructure by its homogenised stiffness."""

    name = "h8_periodic"
    label = "3-D unit cell (material microstructure)"
    use_when = "To design a 3-D material: maximise bulk or shear modulus, or minimise Poisson's ratio."
    reference = ("Numerical homogenisation: E. Andreassen, C. S. Andreasen, Comput. Mater. Sci. 83 (2014) 488-495."
                 " Papers: https://doi.org/10.1016/j.commatsci.2013.09.006")
    order = 61
    physics = H8PeriodicCell
