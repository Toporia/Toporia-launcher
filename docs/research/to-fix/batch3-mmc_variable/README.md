# MMC variable-thickness bars: unresolved paper comparison

Target: Zhang et al. (2016) variable-thickness MMC: exact numbered component/optimized panel pending.

Difference/gap: Source and code thickness parameter ordering must be aligned before an MMC188 comparison. Tanh/product union and centre sampling are independent choices. The showcase uses GCMMA: with plain MMA (Toporia's and pyMOTO's) the design stayed 0.3-0.7 % over the volume budget for 600 steps, because the bar volume is strongly nonlinear in the bar parameters; GCMMA's conservative approximation ends exactly on it, at lower compliance.

Recorded execution: 300 steps; iteration limit (300). Fresh final compliance 237.07762; physical fraction 0.49999993; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Recover a numbered variable-thickness MMC panel and thickness ordering, then align union, Heaviside sampling and optimizer settings with MMC188.

[Figure](../../evidence/batch3/mmc_variable/figure.png) · [Numerical report](../../evidence/batch3/mmc_variable/report.json) · [Description and math](../../evidence/batch3/mmc_variable/description.html)
