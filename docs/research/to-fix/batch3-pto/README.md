# PTO sensitivity-proxy variant: unresolved paper comparison

Target: Biyikli-To (2015), Figure 3 MBB PTOc panel (120 by 40, fraction 0.35).

Difference/gap: The published PTOc uses element compliance allocation; a negative filtered sensitivity is not proportional to it across varying density. Current q=3/relax=0.2 also differs from the source study. No source replication claimed.

Recorded execution: 94 steps; design change 0.00976 < tol 0.01. Fresh final compliance 212.83723; physical fraction 0.5; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: None for the algorithm: the original is the separate ptoc updater, which reproduces the captured author run exactly (evidence/batch3/ptoc). This sensitivity-proxy variant stays a declared, different method; its Figure 3 comparison below records that difference.

[Figure](../../evidence/batch3/pto/figure.png) · [Numerical report](../../evidence/batch3/pto/report.json) · [Description and math](../../evidence/batch3/pto/description.html)

## Native Figure 3 attempt

Author PTOc stopped at 170 iterations; the Toporia variant reached 600. Relative fresh-compliance difference: 21.2626%; max density difference: 0.998458. Both use the paper's distributed three-node loads/supports and fraction 0.35. The common physics check on the author field matches its printed compliance within rounding.

[Native comparison figure](../../evidence/batch3/pto/paper-attempt/figure.png) · [Comparison report](../../evidence/batch3/pto/paper-attempt/report.json)
