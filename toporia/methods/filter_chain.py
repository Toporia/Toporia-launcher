# filter_chain.py — factory functions for the filter pipeline
#
# Exposes two public helpers:
#
#   build_filter_chain(filter_specs, problem, config)
#       Creates a FilterChain from the GUI pipeline spec list.
#       Empty list → caller uses no chain (raw optimiser output).
#
#   DensityFilterPipeline
#       Small adapter used by density_top88.py to keep filter bookkeeping out
#       of the core OC update.
#
# Individual filter classes live in methods/filters/ (one file per filter).
# FilterChain and the Filter ABC live in methods/filters/filter_base.py.

from .filters import (
    Filter, FilterChain,
    DensityFilter, SensitivityFilter,
    HeavisideFilter, MillingFilter, AMFilter, RoutingRadiusFilter, SymmetryFilter,
)

__all__ = [
    "Filter", "FilterChain",
    "DensityFilter", "SensitivityFilter",
    "HeavisideFilter", "MillingFilter", "AMFilter", "RoutingRadiusFilter",
    "SymmetryFilter",
    "DensityFilterPipeline",
    "build_filter_chain",
]


def build_filter_chain(filter_specs, problem, config):
    """Instantiate a FilterChain from a list of spec dicts and call setup.

    Each spec must have "type" in
    {"density","sensitivity","heaviside","milling","am","routing","symmetry"} plus
    type-specific optional parameters.  Examples:

      {"type": "density"}
      {"type": "density",    "rmin": 2.0}
      {"type": "heaviside",  "beta": 1.0, "eta": 0.5, "beta_max": 32, "beta_interval": 25}
      {"type": "milling",    "directions": [0, 2], "P": 20}
      {"type": "am",         "direction": "S"}
      {"type": "routing",    "radius_mm": 2.0, "P": 20, "start_iter": 20, "ramp_iters": 20, "threshold": 0.05}
      {"type": "symmetry",   "axis": "left_right"}
    """
    _builders = {
        "density":     lambda s: DensityFilter(rmin=s.get("rmin")),
        "sensitivity": lambda s: SensitivityFilter(rmin=s.get("rmin")),
        "heaviside":   lambda s: HeavisideFilter(
            beta=s.get("beta", 1.0),
            eta=s.get("eta", 0.5),
            beta_max=s.get("beta_max", 32.0),
            beta_interval=s.get("beta_interval", 25),
        ),
        "milling":     lambda s: MillingFilter(
            directions=s.get("directions", [0]),
            P=s.get("P", 20),
        ),
        "am":          lambda s: AMFilter(
            direction=s.get("direction", 0),
            overhang_angle=s.get("overhang_angle", 45.0),
        ),
        "routing":     lambda s: RoutingRadiusFilter(
            radius_mm=s.get("radius_mm", 2.0),
            P=s.get("P", 20),
            start_iter=s.get("start_iter", 20),
            ramp_iters=s.get("ramp_iters", 20),
            threshold=s.get("threshold", 0.05),
        ),
        "symmetry":    lambda s: SymmetryFilter(
            axis=s.get("axis", "left_right"),
        ),
    }
    filters = []
    for spec in filter_specs:
        t = spec.get("type", "density")
        if t not in _builders:
            raise ValueError(
                f"Unknown filter type {t!r}.  Available: {list(_builders)}"
            )
        filters.append(_builders[t](spec))
    chain = FilterChain(filters)
    chain.setup(problem, config)
    return chain


class DensityFilterPipeline:
    """Filter adapter for density-based topology optimization.

    It owns the FilterChain and the fixed/passive mask enforcement so the density
    optimizer can stay focused on FEA, sensitivities, and the OC update.
    """

    def __init__(self, problem, config):
        specs = getattr(config, "filter_specs", None) or []
        self.problem = problem
        self.chain = build_filter_chain(specs, problem, config) if specs else None

    def physical_density(self, design):
        x_phys = self.chain.forward(design).copy() if self.chain else design.copy()
        x_phys[self.problem.passive_elements] = 1.0
        x_phys[self.problem.void_elements] = 0.0
        return x_phys

    def sensitivities(self, dc, dv):
        if self.chain is None:
            return dc, dv
        return self.chain.backward(dc), self.chain.backward_volume(dv)

    def step(self, iteration):
        if self.chain is not None:
            self.chain.step(iteration)
