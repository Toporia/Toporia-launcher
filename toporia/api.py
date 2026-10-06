# toporia/api.py — what a plugin may import.  Everything here is kept stable.
#
# A plugin that lives in another package (see framework/registry.py for how it is
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
# it with AssembledModel, three lines (see plugins/models/q4.py).

from toporia.checks import conformance
from toporia.framework.optimisers.external_loop import ExternalOptimizer, Verdict
from toporia.framework.optimisers.flat_view import VOLUME_BUDGET, FlatProblem
from toporia.framework.params import Param
from toporia.framework.parts.composition import compose
from toporia.framework.parts.filter import Filter
from toporia.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod
from toporia.framework.parts.model import ConstraintValue, Evaluation, Model
from toporia.framework.parts.physics import ELASTIC_ENERGY, STRESS, Physics
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response, ResponseValue
from toporia.framework.parts.updater import Updater
from toporia.framework.registry import install_hint, missing_dependencies
from toporia.plugins.filters import FILTERS
from toporia.plugins.methods import METHODS, method_class
from toporia.plugins.models import MODELS
from toporia.plugins.models.assembled import AssembledModel
from toporia.plugins.responses import RESPONSES
from toporia.plugins.updaters import UPDATERS

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
