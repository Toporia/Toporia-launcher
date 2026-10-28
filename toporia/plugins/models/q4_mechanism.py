"""Q4 port-spring elasticity as a composable density model."""

from toporia.plugins.models.assembled import AssembledModel
from toporia.plugins.physics.q4_mechanism import Q4Mechanism


class Q4MechanismModel(AssembledModel):
    """Toporia's 2-D Q4 solver with input/output port springs, for compliant mechanisms such as a force inverter."""
    name = "q4_mechanism"
    label = "2-D Q4 compliant mechanism (Toporia)"
    use_when = "For compliant mechanisms (grippers, force inverters): input and output ports with springs."
    order = 13
    physics = Q4Mechanism
    reference = (
        'O. Sigmund, "On the Design of Compliant Mechanisms Using Topology Optimization", '
        'Mechanics of Structures and Machines 25 (1997) 493-524. '
        'Own linear Q4 implementation with point springs. '
        'Papers: https://doi.org/10.1080/08905459708945415'
    )
