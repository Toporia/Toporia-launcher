# library/methods/compositions.py — methods assembled from a model and an updater.
#
# A gradient-based method is two independent choices (core/composition.py):
#
#     model    what is optimised, and how its gradients are computed
#              (library/models: Toporia's Q4 solver, or a pyMOTO network)
#     updater  how the design moves, given those gradients
#              (library/updaters: OC, MMA, pyMOTO's MMA and GCMMA)
#
# Each class below is one pairing offered in the method menu.  Any model works
# with any updater, so a new combination is a few lines here — and
# tests/test_composition.py runs every pairing, registered or not.

from toporia.core.composition import ComposedMethod
from toporia.library.models.pymoto_compliance import PymotoComplianceModel
from toporia.library.models.q4_compliance import Q4ComplianceModel
from toporia.library.updaters.mma import MMAUpdater
from toporia.library.updaters.oc import OCUpdater
from toporia.library.updaters.pymoto_optimizers import PymotoGCMMAUpdater, PymotoMMAUpdater


class DensityOC(ComposedMethod):
    """The top88 method: Q4 compliance, optimality-criteria update."""
    name = "density"
    label = "SIMP density (OC)"
    order = 10
    model = Q4ComplianceModel
    updater = OCUpdater


class DensityMMA(ComposedMethod):
    """The top88mma method: Q4 compliance, method of moving asymptotes."""
    name = "density_mma"
    label = "SIMP density (MMA)"
    aliases = ("mma",)
    order = 20
    model = Q4ComplianceModel
    updater = MMAUpdater


class PymotoMMA(ComposedMethod):
    """Physics and sensitivities by a pyMOTO network, update by pyMOTO's MMA."""
    name = "pymoto"
    label = "SIMP density via pyMOTO (MMA)"
    order = 40
    model = PymotoComplianceModel
    updater = PymotoMMAUpdater


class DensityGCMMA(ComposedMethod):
    """Toporia's Q4 physics and filters, updated by pyMOTO's globally convergent MMA."""
    name = "density_gcmma"
    label = "SIMP density (GCMMA, pyMOTO)"
    order = 50
    model = Q4ComplianceModel
    updater = PymotoGCMMAUpdater
