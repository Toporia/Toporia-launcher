# BESO hard kill: unresolved paper comparison

Target: Huang-Xie BESO beam examples: exact panel and history pending.

Difference/gap: Hard kill uses exact design void bounds but the physics retains ersatz stiffness. Sensitivity histories, additions and discrete ties matter.

Recorded execution: 59 steps; Q4Model_HardKillBESOUpdater reported its own convergence criterion. Fresh final compliance 259.1528; physical fraction 0.49901328; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: Recover a hard-kill source example and distinguish exact design removal from the remaining ersatz stiffness, then align neighbor-sensitivity reintroduction.

[Figure](../../evidence/batch3/beso_hard/figure.png) · [Numerical report](../../evidence/batch3/beso_hard/report.json) · [Description and math](../../evidence/batch3/beso_hard/description.html)
