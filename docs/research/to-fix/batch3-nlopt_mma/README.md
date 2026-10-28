# MMA through NLopt: unresolved paper comparison

Target: Svanberg MMA/GCMMA numerical examples: numbered panel and original problem inputs still to recover.

Difference/gap: The common MBB diagnostic is not a Svanberg paper figure. Library algorithms, scaling, safeguards and stopping rules differ; matching final compliance alone would not establish algorithm equivalence.

Recorded execution: 199 steps; design change 0 < tol 0.01. Fresh final compliance 211.54497; physical fraction 0.49999997; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Align an original MMA/CCSA source example with NLopt's safeguarded variant, tolerances and evaluation callback convention.

[Figure](../../evidence/batch3/nlopt_mma/figure.png) · [Numerical report](../../evidence/batch3/nlopt_mma/report.json) · [Description and math](../../evidence/batch3/nlopt_mma/description.html)
