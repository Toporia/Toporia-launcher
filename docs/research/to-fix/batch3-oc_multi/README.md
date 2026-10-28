# OC with several multipliers: unresolved paper comparison

Target: Zhou-Rozvany (1991) COC examples: panel/inputs pending.

Difference/gap: Toporia's cyclic-bisection variant does not establish feasibility or convergence of general signed-gradient constraints. The stress limit is 0.8 x the compliance design's peak; it is met only with the small move limit 0.02 (0.3 % over at 0.05), and the earlier limit of 0.27 x the peak cannot be met with half the material at a point load.

Recorded execution: 300 steps; iteration limit (300). Fresh final compliance 225.4166; physical fraction 0.5; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: First establish feasibility for the selected stress limit and distributed-load mesh. The recorded point-load companion violates stress despite meeting volume; then align an original multi-OC example.

[Figure](../../evidence/batch3/oc_multi/figure.png) · [Numerical report](../../evidence/batch3/oc_multi/report.json) · [Description and math](../../evidence/batch3/oc_multi/description.html)
