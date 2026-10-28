# MMA: local one-budget variant: unresolved paper comparison

Target: Svanberg MMA/GCMMA numerical examples: numbered panel and original problem inputs still to recover.

Difference/gap: The common MBB diagnostic is not a Svanberg paper figure. Library algorithms, scaling, safeguards and stopping rules differ; matching final compliance alone would not establish algorithm equivalence.

Recorded execution: 76 steps; Q4Model_MMAUpdater reported its own convergence criterion. Fresh final compliance 248.73245; physical fraction 0.5; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Recover a Svanberg numerical example with original bounds/initial values, then compare the local one-budget coefficients and asymptote history; the current MBB solve is only a diagnostic.

[Figure](../../evidence/batch3/mma/figure.png) · [Numerical report](../../evidence/batch3/mma/report.json) · [Description and math](../../evidence/batch3/mma/description.html)
