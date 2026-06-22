# methods/filters/__init__.py — re-exports all filter classes for convenient import
#
# Usage from outside this package:
#   from methods.filters import Filter, FilterChain, DensityFilter, ...
#
# Individual filter modules live in this directory:
#   filter_base.py        — Filter ABC + FilterChain
#   filter_density.py     — DensityFilter   (weighted neighbourhood average)
#   filter_sensitivity.py — SensitivityFilter (heuristic sensitivity weighting)
#   filter_heaviside.py   — HeavisideFilter  (projection, beta continuation)
#   filter_milling.py     — MillingFilter    (CNC accessibility constraint)
#   filter_am.py          — AMFilter         (additive manufacturing overhang)
#
# The factory function (build_filter_chain) lives in
# methods/filter_chain.py so that the package name and module name don't collide.

from .filter_base        import Filter, FilterChain
from .filter_density     import DensityFilter
from .filter_sensitivity import SensitivityFilter
from .filter_heaviside   import HeavisideFilter
from .filter_milling     import MillingFilter
from .filter_am          import AMFilter
from .filter_routing     import RoutingRadiusFilter
from .filter_symmetry    import SymmetryFilter

__all__ = [
    "Filter", "FilterChain",
    "DensityFilter", "SensitivityFilter",
    "HeavisideFilter",
    "MillingFilter",
    "AMFilter",
    "RoutingRadiusFilter",
    "SymmetryFilter",
]
