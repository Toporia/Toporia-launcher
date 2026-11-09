# toporia_core/api.py — what a plugin may import.  Everything here is kept stable.
#
# A plugin that lives in another package (see toporia_core/framework/registry.py for how it is
# found) should import from this module only:
#
#     from toporia_core.api import Updater, Param
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
#   representation  Representation           toporia.representations
#   filter     Filter                        toporia.filters
#   interpolation  Interpolation             toporia.interpolations
#   response   Response                      toporia.responses
#   schedule   Schedule                      toporia.schedules
#   postprocessor  PostProcessor             toporia.postprocessors
#   method     OptimizationMethod            toporia.methods
#
# A physics engine (Physics) is not registered on its own: declare a model on
# it with AssembledModel, three lines (see toporia_library/models/q4.py).

from toporia_core.checks import conformance
from toporia_core.framework.optimisers.external_loop import ExternalOptimizer, Verdict
from toporia_core.framework.optimisers.flat_view import VOLUME_BUDGET, FlatProblem
from toporia_core.framework.params import Param
from toporia_core.framework.parts.assembled import AssembledModel
from toporia_core.framework.parts.composition import compose
from toporia_core.framework.parts.filter import Filter
from toporia_core.framework.parts.interpolation import Interpolation
from toporia_core.framework.parts.method import OBJECTIVE, Capabilities, OptimizationMethod
from toporia_core.framework.parts.model import ConstraintValue, Evaluation, Model
from toporia_core.framework.parts.physics import (
    BUCKLING,
    ELASTIC_ENERGY,
    POINT_DISPLACEMENT,
    STRESS,
    BucklingPhysics,
    Physics,
    PointDisplacementPhysics,
)
from toporia_core.framework.parts.postprocess import PostProcessor, Result
from toporia_core.framework.parts.representation import Representation
from toporia_core.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response, ResponseValue
from toporia_core.framework.parts.schedule import Schedule, change_parameter
from toporia_core.framework.parts.updater import Updater
from toporia_core.framework.parts.variants import VariantModel
from toporia_core.framework.registries import (
    FILTERS,
    INTERPOLATIONS,
    METHODS,
    MODELS,
    POSTPROCESSORS,
    REPRESENTATIONS,
    RESPONSES,
    SCHEDULES,
    UPDATERS,
    method_class,
)
from toporia_core.framework.registry import install_hint, missing_dependencies

#: Every registry, by plugin kind.
REGISTRIES = {"model": MODELS, "updater": UPDATERS, "representation": REPRESENTATIONS, "filter": FILTERS,
              "interpolation": INTERPOLATIONS, "response": RESPONSES, "schedule": SCHEDULES, "method": METHODS,
              "postprocessor": POSTPROCESSORS}


def plugin_errors():
    """[(kind, where, message)] for every plugin that failed to load, across all registries."""
    errors = []
    for kind, registry in REGISTRIES.items():
        errors += [(kind, where, message) for where, message in registry.errors]
    return errors


__all__ = [
    # what is optimised
    "Model", "AssembledModel", "Physics", "ELASTIC_ENERGY", "STRESS", "BUCKLING", "BucklingPhysics",
    "POINT_DISPLACEMENT", "PointDisplacementPhysics",
    "Evaluation", "ConstraintValue",
    # how the design moves
    "Updater", "ExternalOptimizer", "Verdict", "FlatProblem", "VOLUME_BUDGET",
    # design variables, regularisation, material law and responses
    "Representation", "Filter", "Interpolation", "Response", "ResponseValue", "OBJECTIVE_ROLE", "CONSTRAINT_ROLE",
    # what changes during a run, and several versions of one design
    "Schedule", "change_parameter", "VariantModel",
    # what is made of a finished design
    "PostProcessor", "Result",
    # whole methods
    "OptimizationMethod", "Capabilities", "OBJECTIVE", "compose", "method_class",
    # declarations, discovery, checking
    "Param", "REGISTRIES", "METHODS", "MODELS", "UPDATERS", "REPRESENTATIONS", "FILTERS", "INTERPOLATIONS",
    "RESPONSES", "SCHEDULES", "POSTPROCESSORS",
    "missing_dependencies", "install_hint", "plugin_errors", "conformance",
]
