# SLSQP through SciPy: unresolved paper comparison

Target: Original optimizer numerical example: identified figure and complete inputs pending; library documentation reviewed separately.

Difference/gap: The coarse MBB companion checks adapter execution, not the source optimizer's paper figure or global optimality. Small steps, library success and feasibility are separate observations.

Recorded execution: 90 steps; design change 0.00573 < tol 0.01. Fresh final compliance 254.8493; physical fraction 0.5; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Recover a Kraft numerical example and align normalization, bound handling, tolerances and accepted-iterate callbacks.

[Figure](../../evidence/batch3/scipy_slsqp/figure.png) · [Numerical report](../../evidence/batch3/scipy_slsqp/report.json) · [Description and math](../../evidence/batch3/scipy_slsqp/description.html)
