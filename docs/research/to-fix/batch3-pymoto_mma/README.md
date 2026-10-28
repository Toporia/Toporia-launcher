# MMA through pyMOTO: unresolved paper comparison

Target: Svanberg MMA/GCMMA numerical examples: numbered panel and original problem inputs still to recover.

Difference/gap: The common MBB diagnostic is not a Svanberg paper figure. Library algorithms, scaling, safeguards and stopping rules differ; matching final compliance alone would not establish algorithm equivalence.

Recorded execution: 109 steps; design change 0.0087 < tol 0.01. Fresh final compliance 210.66116; physical fraction 0.49999992; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Use an identified MMA2007 reference example, not an assumed MMA1987 trajectory; align objective scaling and record every model evaluation.

[Figure](../../evidence/batch3/pymoto_mma/figure.png) · [Numerical report](../../evidence/batch3/pymoto_mma/report.json) · [Description and math](../../evidence/batch3/pymoto_mma/description.html)
