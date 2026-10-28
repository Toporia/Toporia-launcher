# Local-stress augmented Lagrangian: unresolved paper comparison

Target: Giraldo-Londono-Paulino PolyStress examples: matching mesh, stress relaxation and numbered panel pending.

Difference/gap: Q4 ersatz cells and the current density-relaxed stresses differ from PolyStress polygonal meshes. Inspect the exact stress ratio, not just small motion.

Recorded execution: 300 steps; iteration limit (300). Fresh final compliance 223.56887; physical fraction 0.49994589; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: False. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Establish a feasible local-stress benchmark with aligned stress relaxation, mesh/load support and multiplier update schedule before comparing a PolyStress panel.

[Figure](../../evidence/batch3/augmented_lagrangian/figure.png) · [Numerical report](../../evidence/batch3/augmented_lagrangian/report.json) · [Description and math](../../evidence/batch3/augmented_lagrangian/description.html)
