# plugins/models/q4_buckling.py — the 2-D Q4 solver with linearised buckling as a model.
#
# The same pipeline as plugins/models/q4.py (filters, material law, responses),
# on an engine that also answers the BUCKLING question, so the buckling load
# response (plugins/responses/buckling.py) can be minimised or constrained next
# to compliance, volume and stress.  pyMOTO has no buckling module, so there is
# no pyMOTO version of this model.

from toporia.plugins.physics.q4_buckling import Q4Buckling

from .assembled import AssembledModel


class Q4BucklingModel(AssembledModel):
    """Toporia's 2-D Q4 solver with linearised buckling: compliance, volume, stress and buckling load."""

    name = "q4_buckling"
    label = "2-D Q4 with buckling (Toporia)"
    use_when = "For 2-D structures in compression where buckling must be prevented."
    reference = (
        'F. Ferrari, O. Sigmund, J. K. Guest, "Topology optimization with linearized buckling'
        ' criteria in 250 lines of Matlab", Struct. Multidisc. Optim. 63 (2021) 3045-3066'
        " (the method, written here from the paper's description)."
        ' Papers: https://doi.org/10.1007/s00158-021-02854-x'
    )
    order = 11
    physics = Q4Buckling
