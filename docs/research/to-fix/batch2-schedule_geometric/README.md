# Geometric beta continuation: unresolved research comparison

Target: Wang et al. (2011), section 4 continuation accompanying Figures 3-4.

Numerical issue: **resolved** (28 October 2026). The companion ran on OC with move 0.2 and ended at compliance 3.35e8 after members flipped at beta 128; on MMA with move 0.1 (the paper's optimizer) it converges at iteration 351 with compliance 189.27.

Reason: A schedule plot verifies the fixed-interval rule only. It omits early increases at convergence and does not reproduce an optimized paper design.

Numerical checks: True. A passing engineering check is not a paper reproduction.

Next: Match the paper's optimizer and early-convergence trigger as well as its 50-step clock; the bounded OC companion is not converged.

[Figure and numerical report](../../evidence/batch2/schedule_geometric/report.json) · [Generated figure](../../evidence/batch2/schedule_geometric/figure.png)
