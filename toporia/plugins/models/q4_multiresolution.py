"""Fine-density/coarse-displacement Q4 model, independently derived from MTOP."""

from toporia.plugins.physics.q4_multiresolution import Q4Multiresolution

from .assembled import AssembledModel


class Q4MultiresolutionModel(AssembledModel):
    """Nested 2-D multiresolution elasticity; fine-grid filters and representations."""

    name = "q4_multiresolution"
    label = Q4Multiresolution.label
    reference = Q4Multiresolution.reference
    order = 10
    physics = Q4Multiresolution
