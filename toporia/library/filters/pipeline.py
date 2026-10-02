# library/filters/pipeline.py — build a filter pipeline from spec dicts
#
#   build_filter_chain(filter_specs, problem, solver)
#       Looks each spec's "type" up in the FILTERS registry, validates its
#       parameters against the filter's Param declarations, and returns a set-up
#       FilterChain.  Empty list → caller uses no chain (raw optimiser output).
#
#   DensityFilterPipeline
#       Small adapter used by density models (library/models) to keep filter
#       bookkeeping out of their physics.
#
# Individual filter classes live next to this file, one per module; FilterChain
# and the Filter ABC live in filter_base.py.

import numpy as np

from toporia.core.params import resolve_params

from . import FILTERS
from .filter_base import FilterChain

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
        # Elements whose bounds coincide are overwritten after filtering, so the
        # physical density there does not depend on the design at all.
        self.pinned = problem.upper_bound <= problem.lower_bound

    def physical_density(self, design):
        """Filter the design, then clamp it to the problem's per-element bounds.

        Clipping to lower_bound/upper_bound is equivalent to overwriting the
        passive and void masks, but it is the same operation the optimisers use
        so the enforcement cannot drift between the two.
        """
        x_phys = self.chain.forward(design).copy() if self.chain else design.copy()
        return np.clip(x_phys, self.problem.lower_bound, self.problem.upper_bound)

    def sensitivities(self, dc, dv):
        """Map the objective and volume sensitivities (w.r.t. the physical density) to the design.

        The pinned elements' entries are dropped before the filter adjoint:
        physical_density overwrites them after filtering, so a change of the
        design reaches them only through that overwrite, which is constant.
        Passing them through the adjoint spread their sensitivity onto the
        free neighbours and made gradients near holes and solid rings wrong.
        """
        if self.chain is None:
            return dc, dv
        return self.chain.backward(self._unpinned(dc)), self.chain.backward_volume(self._unpinned(dv))

    def sensitivity(self, ds):
        """Map one more response's sensitivity (a constraint's) back to the design."""
        return ds if self.chain is None else self.chain.backward(self._unpinned(ds))

    def _unpinned(self, sensitivity):
        return np.where(self.pinned, 0.0, sensitivity)

    def step(self, iteration):
        if self.chain is not None:
            self.chain.step(iteration)
