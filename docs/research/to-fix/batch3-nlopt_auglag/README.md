# Augmented Lagrangian through NLopt: unresolved paper comparison

Target: Original optimizer numerical example: identified figure and complete inputs pending; library documentation reviewed separately.

Difference/gap: The coarse MBB companion checks adapter execution, not the source optimizer's paper figure or global optimality. Small steps, library success and feasibility are separate observations.

Recorded execution: 101 steps; Augmented Lagrangian + L-BFGS (NLopt) finished: FTOL_REACHED. Fresh final compliance 254.54401; physical fraction 0.49999997; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Choose an identified constrained source example and align the outer multiplier and inner L-BFGS budgets; a library FTOL flag alone is insufficient.

[Figure](../../evidence/batch3/nlopt_auglag/figure.png) · [Numerical report](../../evidence/batch3/nlopt_auglag/report.json) · [Description and math](../../evidence/batch3/nlopt_auglag/description.html)
