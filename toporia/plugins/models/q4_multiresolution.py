"""Fine-density/coarse-displacement Q4 model, independently derived from MTOP."""

from toporia.plugins.physics.q4_multiresolution import Q4Multiresolution

from .assembled import AssembledModel


class Q4MultiresolutionModel(AssembledModel):
    """Nested 2-D multiresolution elasticity; fine-grid filters and representations."""

    name = "q4_multiresolution"
    label = Q4Multiresolution.label
    use_when = (
        "To get a finer design than the analysis mesh at lower cost. Can over-predict stiffness; always "
        "compare with a fine-mesh analysis of the final design."
    )
    reference = Q4Multiresolution.reference
    order = 10
    physics = Q4Multiresolution
