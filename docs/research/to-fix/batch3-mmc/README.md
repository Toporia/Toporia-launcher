# MMC constant-thickness bars: unresolved paper comparison

Target: Guo et al., arXiv:1404.4820, Figure 8 component and zero contour; own geometry parameters.

Difference/gap: Zero-contour construction is a controlled instance, not the paper image coordinates or optimized cantilever. Product union/tanh differ from the reference implementation.

Recorded execution: 84 steps; design change 0.00592 < tol 0.01. Fresh final compliance 256.09588; physical fraction 0.50008252; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Recover Figure 8's geometry/field normalization or keep this as an own instance. A final-design comparison also needs the reference maximum union, projection and analysis sampling aligned.

[Figure](../../evidence/batch3/mmc/figure.png) · [Numerical report](../../evidence/batch3/mmc/report.json) · [Description and math](../../evidence/batch3/mmc/description.html)
