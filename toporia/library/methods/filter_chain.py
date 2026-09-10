# filter_chain.py — build a filter pipeline from spec dicts
#
#   build_filter_chain(filter_specs, problem, solver)
#       Looks each spec's "type" up in the FILTERS registry, validates its
#       parameters against the filter's Param declarations, and returns a set-up
#       FilterChain.  Empty list → caller uses no chain (raw optimiser output).
#
#   DensityFilterPipeline
#       Small adapter used by the density methods to keep filter bookkeeping out
#       of their update rules.
#
# Individual filter classes live in methods/filters/ (one file per filter).
# FilterChain and the Filter ABC live in methods/filters/filter_base.py.

import numpy as np

from toporia.core.params import resolve_params

from .filters import FILTERS, FilterChain

__all__ = ["DensityFilterPipeline", "build_filter_chain"]


def build_filter_chain(filter_specs, problem, solver):
    """Instantiate a FilterChain from a list of spec dicts and call setup.

    Each spec is {"type": <filter name>, <param>: <value>, ...}, for example
    {"type": "heaviside", "beta": 2.0}.  Parameters left out take the defaults
    declared on the filter class, and an unknown parameter is an error.  The
    available types are FILTERS.names().
    """
    filters = []
    for spec in filter_specs:
        spec = dict(spec)
        cls = FILTERS.get(spec.pop("type", "density"))
        filters.append(cls(**resolve_params(f"filter {cls.name!r}", cls.params, spec)))
    chain = FilterChain(filters)
    chain.setup(problem, solver)
    return chain


class DensityFilterPipeline:
    """Filter adapter for density-based topology optimization.

    It owns the FilterChain and the fixed/passive mask enforcement so the density
    optimizer can stay focused on FEA, sensitivities, and the OC update.
    """

    def __init__(self, problem, solver):
        specs = solver.filter_specs
        self.problem = problem
        self.chain = build_filter_chain(specs, problem, solver) if specs else None

    def physical_density(self, design):
        """Filter the design, then clamp it to the problem's per-element bounds.

        Clipping to lower_bound/upper_bound is equivalent to overwriting the
        passive and void masks, but it is the same operation the optimisers use
        so the enforcement cannot drift between the two.
        """
        x_phys = self.chain.forward(design).copy() if self.chain else design.copy()
        return np.clip(x_phys, self.problem.lower_bound, self.problem.upper_bound)

    def sensitivities(self, dc, dv):
        if self.chain is None:
            return dc, dv
        return self.chain.backward(dc), self.chain.backward_volume(dv)

    def step(self, iteration):
        if self.chain is not None:
            self.chain.step(iteration)
