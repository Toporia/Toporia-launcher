# RBF level-set evolution: unresolved paper comparison

Target: Wei et al. (2018) TOPRBF cantilever: numbered panel/settings pending.

Difference/gap: Mean instead of median energy normalization, guarded rescaling and clipped field make this a numerical variant. Dense node matrices limit mesh size.

Recorded execution: 139 steps; LevelSetRBFMethod reported its own convergence criterion. Fresh final compliance 182.51911; physical fraction 0.49984694; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Compare against a source TOPRBF panel with its median normalization and original rescaling; the mean-normalized clipped variant cannot be called an exact port.

[Figure](../../evidence/batch3/levelset/figure.png) · [Numerical report](../../evidence/batch3/levelset/report.json) · [Description and math](../../evidence/batch3/levelset/description.html)
