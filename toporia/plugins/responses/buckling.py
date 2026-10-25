# plugins/responses/buckling.py — the lowest linearised buckling load factors.
#
# The load factor λ is the multiple of the applied load at which the structure
# buckles (framework/parts/physics.py, BUCKLING).  A design has several modes,
# and during optimisation the lowest ones swap places and become equal, where a
# single eigenvalue is not differentiable.  So the response aggregates the
# lowest few modes of every load case with a p-norm of their reciprocals:
#
#     P = ( Σ_j (1/λ_j)^p )^(1/p)  ≥  1/λ_1,     equal to it as p grows
#     g = λ_ref · P − 1
#
# As a constraint, g ≤ 0 means "all modes buckle above λ_ref times the load"
# (a little conservative while modes are close: P overestimates 1/λ_1 by at
# most n^(1/p)).  As an objective, minimising g maximises the load factor; λ_ref
# then only scales the value, so set it near the expected load factor to keep
# the objective of order one.  The exact λ_1 is reported as `buckling_load`.
#
# Everything engine-specific is in the physics (buckling_factors,
# buckling_sensitivity), so this file serves every engine that provides BUCKLING.
# The aggregation is the one Ferrari, Sigmund & Guest (SMO 63 (2021) 3045-3066)
# use in spirit (several lowest modes, so repeated eigenvalues are harmless);
# the p-norm form itself is a choice made here.

import numpy as np

from toporia.framework.params import Param
from toporia.framework.parts.physics import BUCKLING
from toporia.framework.parts.response import CONSTRAINT_ROLE, OBJECTIVE_ROLE, Response, ResponseValue


class BucklingLoad(Response):
    """λ_ref · ‖1/λ_i‖_p − 1 over the lowest few buckling modes; minimised, it maximises the buckling load."""
    name = "buckling_load"
    label = "Buckling load factor"
    reference = (
        'F. Ferrari, O. Sigmund, J. K. Guest, "Topology optimization with linearized buckling'
        ' criteria in 250 lines of Matlab", Struct. Multidisc. Optim. 63 (2021) 3045-3066.'
        ' Papers: https://doi.org/10.1007/s00158-021-02854-x'
    )
    order = 40
    roles = (OBJECTIVE_ROLE, CONSTRAINT_ROLE)
    params = (
        Param("min_load", 1.0, "Required load factor",
              "The load factor the design must reach (constraint: all modes above it). As an "
              "objective it only scales the value; set it near the load factor you expect.",
              min=1e-9, max=1e12, step=0.1, decimals=4),
        Param("modes", 6, "Modes",
              "How many of the lowest buckling modes enter the aggregate, per load case. More modes "
              "cope better with modes that cross, and cost more.",
              min=1, max=20, step=1, decimals=0),
        Param("p", 8.0, "P-norm exponent",
              "Aggregation sharpness. Higher follows the lowest mode more closely but is harder to optimise.",
              min=1.0, max=64.0, step=1.0, decimals=1),
    )
    requires = (BUCKLING,)
    schedulable = ("p",)

    def evaluate(self, state, gradient=True):
        physics, settings = self.physics, self.settings
        p, reference, modes = settings["p"], settings["min_load"], int(settings["modes"])

        factors = []   # (λ, load case, mode index)
        for case in range(len(state.weights)):
            for i, lam in enumerate(physics.buckling_factors(state, case, modes)):
                factors.append((lam, case, i))
        if not factors:
            # No compression anywhere: the structure cannot buckle, so the constraint is slack.
            zero = None if not gradient else np.zeros_like(state.density, dtype=float)
            return ResponseValue(-1.0, zero, -1.0, {"buckling_load": float("inf")})

        lam = np.array([f[0] for f in factors])
        mu = 1.0 / lam
        top = float(mu.max())
        # The p-norm relative to its largest term, so mu^p cannot overflow.
        norm = top * float(np.sum((mu / top) ** p)) ** (1.0 / p)
        value = reference * norm - 1.0
        lowest = float(lam.min())
        exact = reference / lowest - 1.0
        reported = {"buckling_load": lowest}
        if not gradient:
            return ResponseValue(value, None, exact, reported)

        # With μ_j = 1/λ_j:  dP/dμ_j = (μ_j / P)^(p−1)  and  dμ_j/dλ_j = −μ_j².
        d_norm_d_lambda = -((mu / norm) ** (p - 1.0)) * mu ** 2
        sensitivity = np.zeros_like(state.density, dtype=float)
        for slope, (_, case, i) in zip(d_norm_d_lambda, factors, strict=True):
            sensitivity += slope * physics.buckling_sensitivity(state, case, i)
        return ResponseValue(value, reference * sensitivity, exact, reported)
