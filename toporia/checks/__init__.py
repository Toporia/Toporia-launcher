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
#   Representation field shape and range; start within bounds; backward()
#                  against finite differences; a short run with q4+mma
#   Filter         output shape and range; the adjoint against finite
#                  differences (unless the filter declares exact_adjoint = False)
#   Interpolation  E(0) = Emin, E(1) = E0, increasing; slope() against finite differences
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
#     updater.py · model.py · representation.py · filter.py · interpolation.py · response.py · method.py

import contextlib
import io

from toporia.framework.parts.method import OptimizationMethod
from toporia.framework.parts.model import Model
from toporia.framework.parts.physics import Physics
from toporia.framework.parts.response import Response
from toporia.framework.parts.updater import Updater

from .filter import check_filter
from .interpolation import check_interpolation
from .method import check_method
from .model import check_model, check_physics
from .report import Check, Report
from .representation import check_representation
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
    """The plugins a run is made of, as "kind:name" (see engine.pipeline.pipeline_parts)."""
    from toporia.engine.pipeline import pipeline_parts
    return [f"{kind}:{cls.name}" for kind, cls in pipeline_parts(run)]


def _conformance(plugin, **options):
    if isinstance(plugin, str):
        plugin = _lookup(plugin)
    checks = ((Updater, check_updater), (Model, check_model), (Physics, check_physics),
              (Response, check_response), (OptimizationMethod, check_method))
    for base, check in checks:
        if isinstance(plugin, type) and issubclass(plugin, base):
            return check(plugin, **options)
    from toporia.framework.parts.filter import Filter
    from toporia.framework.parts.interpolation import Interpolation
    if isinstance(plugin, type) and issubclass(plugin, Filter):
        return check_filter(plugin, **options)
    if isinstance(plugin, type) and issubclass(plugin, Interpolation):
        return check_interpolation(plugin, **options)
    from toporia.framework.parts.representation import Representation
    if isinstance(plugin, type) and issubclass(plugin, Representation):
        return check_representation(plugin, **options)
    raise TypeError(f"{plugin!r} is not a Toporia plugin class")


def all_plugins():
    """Every registered plugin, as "kind:name" strings."""
    from toporia.engine.pipeline import registries
    return [f"{kind}:{name}" for kind, registry in registries().items() for name in registry.names()]


def _lookup(text):
    from toporia.engine.pipeline import registries
    found = registries()
    kind, _, name = text.partition(":")
    if kind not in found or not name:
        raise ValueError(f"Name a plugin as kind:name with kind one of {sorted(found)}, got {text!r}")
    return found[kind].get(name)


__all__ = ["Check", "Report", "conformance", "all_plugins", "parts_of", "check_updater",
           "check_model", "check_physics", "check_filter", "check_interpolation", "check_representation",
           "check_response", "check_method"]
