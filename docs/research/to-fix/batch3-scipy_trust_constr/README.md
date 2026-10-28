# Trust-constr through SciPy: unresolved paper comparison

Target: Original optimizer numerical example: identified figure and complete inputs pending; library documentation reviewed separately.

Difference/gap: The coarse MBB companion checks adapter execution, not the source optimizer's paper figure or global optimality. Small steps, library success and feasibility are separate observations.

Recorded execution: 84 steps; design change 0.00622 < tol 0.01. Fresh final compliance 251.47613; physical fraction 0.4999996; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Choose an identified trust-region/interior-point reference example and align SR1 versus BFGS, scaling, radius and barrier stopping criteria.

[Figure](../../evidence/batch3/scipy_trust_constr/figure.png) · [Numerical report](../../evidence/batch3/scipy_trust_constr/report.json) · [Description and math](../../evidence/batch3/scipy_trust_constr/description.html)
