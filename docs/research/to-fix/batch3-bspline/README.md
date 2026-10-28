# B-spline density coefficients: unresolved paper comparison

Target: Qian (2013) B-spline density-space examples: numbered panel and original knots pending.

Difference/gap: A controlled coefficient field and independent basis check do not reproduce an optimized paper topology or its knot refinement study. With only 8 by 4 cubic coefficients (one basis function spanning about 7 cells) the field cannot be sharp and stayed grey (greyness 0.87); the showcase uses 40 by 14 quadratic coefficients and a projection.

Recorded execution: 202 steps; design change 0.00918 < tol 0.01. Fresh final compliance 191.0172; physical fraction 0.49999972; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Recover Qian's numbered example with exact knot vector, coefficient grid, density constraints, FE mesh and stopping rule before comparing optimized shapes.

[Figure](../../evidence/batch3/bspline/figure.png) · [Numerical report](../../evidence/batch3/bspline/report.json) · [Description and math](../../evidence/batch3/bspline/description.html)
