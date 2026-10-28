# Adam moments and volume penalty: unresolved paper comparison

Target: Kingma-Ba Algorithm 1; Figure 1 learning curves require the original data/task and are not this MBB diagnostic.

Difference/gap: Algorithm recurrence agreement is not reproduction of machine-learning figures. Toporia's default beta1=0.5, decaying rate, clipping and volume penalty are topology-specific choices. The showcase uses the default rate 0.05: at 0.01 the decaying rate fell to 0.002 and the design stayed grey (greyness 0.64).

Recorded execution: 300 steps; iteration limit (300). Fresh final compliance 221.52895; physical fraction 0.50059389; budget 0.5; within budget +1e-4: False. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Use original Figure 1 task/data and stochastic gradients for an Adam paper comparison. The deterministic moment probe certifies neither that figure nor topology-specific AL feasibility.

[Figure](../../evidence/batch3/adam/figure.png) · [Numerical report](../../evidence/batch3/adam/report.json) · [Description and math](../../evidence/batch3/adam/description.html)
