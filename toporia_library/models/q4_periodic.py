# toporia_library/models/q4_periodic.py — a 2-D periodic unit cell as a model (multiscale).
#
# The design is one cell of a periodic material; the physics (toporia_library/physics/
# homogenisation.py) gives its homogenised elasticity matrix C^H and ∂C^H/∂ρ, and the responses
# bulk_modulus, shear_modulus and poisson_ratio (toporia_library/responses/homogenised.py) make
# objectives of it.  Filters, material laws and updaters work as on any density model.

from toporia_library.physics.homogenisation import Q4PeriodicCell

from .assembled import AssembledModel


class Q4PeriodicModel(AssembledModel):
    """A 2-D periodic unit cell: design a material microstructure by its homogenised stiffness."""

    name = "q4_periodic"
    label = "2-D unit cell (material microstructure)"
    use_when = "To design a material, not a part: maximise bulk or shear modulus, or minimise Poisson's ratio."
    reference = ("Numerical homogenisation: E. Andreassen, C. S. Andreasen, Comput. Mater. Sci. 83 (2014) 488-495;"
                 " inverse homogenisation: O. Sigmund, Int. J. Solids Struct. 31 (1994) 2313-2329."
                 " Papers: https://doi.org/10.1016/j.commatsci.2013.09.006")
    order = 60
    physics = Q4PeriodicCell
