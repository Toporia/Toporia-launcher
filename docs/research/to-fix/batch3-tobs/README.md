# TOBS integer design steps: unresolved paper comparison

Target: Picelli et al. (2021) TOBS101 examples: numbered panel/inputs pending.

Difference/gap: Linearized feasibility is not nonlinear feasibility; Toporia's relaxation and trust controls must be aligned with the source.

Recorded execution: 36 steps; Q4Model_TOBSUpdater reported its own convergence criterion. Fresh final compliance 257.22246; physical fraction 0.49888994; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Recover TOBS101 panel inputs, switching relaxation and integer-solve tolerances; compare true physical constraint residuals after each MILP update.

[Figure](../../evidence/batch3/tobs/figure.png) · [Numerical report](../../evidence/batch3/tobs/report.json) · [Description and math](../../evidence/batch3/tobs/description.html)
