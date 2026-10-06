# checks — the conformance test a new plugin must pass.
#
# Point it at a class and it checks everything Toporia relies on, then says
# what passed, what failed and why:
#
#     from toporia.checks import conformance
#     conformance(MyUpdater).assert_ok()          # in a test
#     print(conformance(MyUpdater))               # a readable report
#
# or, from the command line:  toporia check updater:my_updater
#
#   every plugin   name, label, parameters that resolve to their defaults
#   Updater        a short run on a problem with holes (finite, inside the
#                  bounds, no thread left behind); a benchmark on the MBB beam,
#                  within `tolerance` of optimality criteria's compliance
#                  and within the volume budget
#   Model          bounds and shapes; volume_of agrees with evaluate; values
#                  without gradients equal values with them; every gradient
#                  against central finite differences
#   Physics        the same, through a model assembled on it
#   Filter         output shape and range; the adjoint against finite
#                  differences (unless the filter declares exact_adjoint = False)
#   Response       its gradient against finite differences, on every engine
#                  that provides the features it requires
#   whole method   a short run (finite, inside the bounds)
#
# The checks only use the public plugin interfaces, so they apply unchanged to
# a plugin that lives in another package.
#
# One module per plugin kind; this file is the entry point:
#
#     report.py    Report and Check: what a check returns
#     common.py    the benchmark problems, finite differences, threads
#     updater.py · model.py · filter.py · response.py · method.py

import contextlib
import io

from toporia.framework.parts.composition import ComposedMethod
from toporia.framework.parts.method import OptimizationMethod
from toporia.framework.parts.model import Model
from toporia.framework.parts.physics import Physics
from toporia.framework.parts.response import Response
from toporia.framework.parts.updater import Updater

from .filter import check_filter
from .method import check_method
from .model import check_model, check_physics
from .report import Check, Report
from .response import check_response
from .updater import check_updater

# ── Entry point ───────────────────────────────────────────────────────────────

def conformance(plugin, **options):
    """Check any plugin class (or "kind:name", e.g. "updater:mma") and return a Report.

    The runs inside print nothing: the report is the output.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        return _conformance(plugin, **options)


def parts_of(run):
    """The plugins a run is made of, as "kind:name": its model and updater (or whole
    method), its filters, and its objective and constraint responses."""
    from toporia.plugins.methods import method_class
    method_cls = method_class(run.solver.method)
    if issubclass(method_cls, ComposedMethod):
        parts = [f"model:{method_cls.model.name}", f"updater:{method_cls.updater.name}"]
    else:
        parts = [f"method:{method_cls.name}"]
    if method_cls.capabilities.accepts_filters:
        parts += [f"filter:{spec.get('type', 'density')}" for spec in run.solver.filter_specs]
    parts.append(f"response:{run.scenario.objective.get('type', 'compliance')}")
    parts += [f"response:{spec['type']}" for spec in run.scenario.constraints]
    return list(dict.fromkeys(parts))


def _conformance(plugin, **options):
    if isinstance(plugin, str):
        plugin = _lookup(plugin)
    checks = ((Updater, check_updater), (Model, check_model), (Physics, check_physics),
              (Response, check_response), (OptimizationMethod, check_method))
    for base, check in checks:
        if isinstance(plugin, type) and issubclass(plugin, base):
            return check(plugin, **options)
    from toporia.framework.parts.filter import Filter
    if isinstance(plugin, type) and issubclass(plugin, Filter):
        return check_filter(plugin, **options)
    raise TypeError(f"{plugin!r} is not a Toporia plugin class")


def all_plugins():
    """Every registered plugin, as "kind:name" strings."""
    from toporia.plugins.filters import FILTERS
    from toporia.plugins.methods import METHODS
    from toporia.plugins.models import MODELS
    from toporia.plugins.responses import RESPONSES
    from toporia.plugins.updaters import UPDATERS
    return [f"{kind}:{name}" for kind, registry in (("model", MODELS), ("updater", UPDATERS),
                                                    ("filter", FILTERS), ("response", RESPONSES),
                                                    ("method", METHODS))
            for name in registry.names()]


def _lookup(text):
    from toporia.plugins.filters import FILTERS
    from toporia.plugins.methods import METHODS
    from toporia.plugins.models import MODELS
    from toporia.plugins.responses import RESPONSES
    from toporia.plugins.updaters import UPDATERS
    registries = {"model": MODELS, "updater": UPDATERS, "filter": FILTERS,
                  "response": RESPONSES, "method": METHODS}
    kind, _, name = text.partition(":")
    if kind not in registries or not name:
        raise ValueError(f"Name a plugin as kind:name with kind one of {sorted(registries)}, got {text!r}")
    return registries[kind].get(name)


__all__ = ["Check", "Report", "conformance", "all_plugins", "parts_of", "check_updater",
           "check_model", "check_physics", "check_filter", "check_response", "check_method"]
