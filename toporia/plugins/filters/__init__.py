"""plugins.filters — density filters, one per module.

Every Filter subclass in this package with a non-empty `name` is found
automatically by the FILTERS registry; there is no list to maintain.  A filter
spec in a config names one by type: {"type": "heaviside", "beta": 2.0}.

    framework/parts/filter.py — the Filter ABC and FilterChain (forward / adjoint passes)
    filter_*.py    — one filter each, declaring its own name, label and params
    pipeline.py    — builds a FilterChain from spec dicts; used by density models
"""

from toporia.framework.parts.filter import Filter, FilterChain
from toporia.framework.registry import Registry

FILTERS = Registry("filter", Filter, __name__)

__all__ = ["FILTERS", "Filter", "FilterChain"]
