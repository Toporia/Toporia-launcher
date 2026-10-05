# toporia/api.py — what a plugin may import.  Everything here is kept stable.
#
# A plugin that lives in another package (see core/registry.py for how it is
# found) should import from this module only:
#
#     from toporia.api import Updater, Param
#
#     class MyUpdater(Updater):
#         name, label = "my_updater", "My updater"
#         params = (Param("step", 0.1, "Step", "How far to move."),)
#         def initialize(self, model, settings): ...
#         def update(self, x, evaluation, completed): ...
#
# Toporia's internal modules may be reorganised; the names below keep their
# meaning, and a change to one of them is a breaking change, said so in the
# release notes.  The plugin kinds, their bases and their entry-point groups:
#
#   kind       base                          entry-point group
#   model      Model (or AssembledModel)     toporia.models
#   updater    Updater (or ExternalOptimizer) toporia.updaters
#   filter     Filter                        toporia.filters
#   response   Response                      toporia.responses
#   method     OptimizationMethod            toporia.methods
#
# A physics engine (Physics) is not registered on its own: declare a model on
# it with AssembledModel, three lines (see library/models/q4.py).

from toporia.core.composition import ConstraintValue, Evaluation, Model, Updater, compose
from toporia.core.contract import OBJECTIVE, Capabilities, OptimizationMethod
from toporia.core.external import ExternalOptimizer, Verdict
from toporia.core.flat import VOLUME_BUDGET, FlatProblem
from toporia.core.params import Param
from toporia.core.physics import ELASTIC_ENERGY, STRESS, Physics
from toporia.core.registry import install_hint, missing_dependencies
from toporia.core.responses import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response, ResponseValue
from toporia.library.filters import FILTERS
from toporia.library.filters.filter_base import Filter
from toporia.library.methods import METHODS, method_class
from toporia.library.models import MODELS
from toporia.library.models.assembled import AssembledModel
from toporia.library.responses import RESPONSES
from toporia.library.updaters import UPDATERS
from toporia.testing import conformance

#: Every registry, by plugin kind.
REGISTRIES = {"model": MODELS, "updater": UPDATERS, "filter": FILTERS,
              "response": RESPONSES, "method": METHODS}


def plugin_errors():
    """[(kind, where, message)] for every plugin that failed to load, across all registries."""
    errors = []
    for kind, registry in REGISTRIES.items():
        errors += [(kind, where, message) for where, message in registry.errors]
    return errors


__all__ = [
    # what is optimised
    "Model", "AssembledModel", "Physics", "ELASTIC_ENERGY", "STRESS", "Evaluation", "ConstraintValue",
    # how the design moves
    "Updater", "ExternalOptimizer", "Verdict", "FlatProblem", "VOLUME_BUDGET",
    # regularisation and responses
    "Filter", "Response", "ResponseValue", "OBJECTIVE_ROLE", "CONSTRAINT_ROLE",
    # whole methods
    "OptimizationMethod", "Capabilities", "OBJECTIVE", "compose", "method_class",
    # declarations, discovery, checking
    "Param", "REGISTRIES", "METHODS", "MODELS", "UPDATERS", "FILTERS", "RESPONSES",
    "missing_dependencies", "install_hint", "plugin_errors", "conformance",
]
