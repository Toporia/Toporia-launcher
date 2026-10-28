# Neural coordinate density: unresolved paper comparison

Target: Chandrasekhar-Suresh TOuNN (2021): architecture/optimization figure alignment pending.

Difference/gap: TOuNN uses batch-normalized LeakyReLU and AMSGrad rather than this tanh/Adam-AL variant. Gray fields, approximate volume and local optima remain possible.

Recorded execution: 300 steps; iteration limit (300). Fresh final compliance 385.76674; physical fraction 0.49963428; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Align a numbered TOuNN panel and its LeakyReLU/batch-normalization/AMSGrad architecture. The present tanh/Adam-AL run remains gray and is not that algorithm.

[Figure](../../evidence/batch3/neural/figure.png) · [Numerical report](../../evidence/batch3/neural/report.json) · [Description and math](../../evidence/batch3/neural/description.html)
