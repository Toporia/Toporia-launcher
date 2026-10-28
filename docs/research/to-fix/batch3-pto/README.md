# PTO sensitivity-proxy variant: unresolved paper comparison

Target: Biyikli-To (2015), Figure 3 MBB PTOc panel (120 by 40, fraction 0.35).

Difference/gap: The published PTOc uses element compliance allocation; a negative filtered sensitivity is not proportional to it across varying density. Current q=3/relax=0.2 also differs from the source study. No source replication claimed.

Recorded execution: 120 steps; iteration limit (120). Fresh final compliance 254.31329; physical fraction 0.5; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: none for the algorithm. **Resolved 28 October 2026:** the original algorithm is now its own updater, `ptoc`, and reproduces the captured author run exactly (169 printed compliances, final density to 1e-8; [evidence](../../evidence/batch3/ptoc/report.json)). This `pto` variant stays a declared, different method; its comparison below is kept as a record of that difference.

[Figure](../../evidence/batch3/pto/figure.png) · [Numerical report](../../evidence/batch3/pto/report.json) · [Description and math](../../evidence/batch3/pto/description.html)

## Native Figure 3 attempt

Author PTOc stopped at 170 iterations; the Toporia variant reached 600. Relative fresh-compliance difference: 21.2626%; max density difference: 0.998458. Both use the paper's distributed three-node loads/supports and fraction 0.35. The common physics check on the author field matches its printed compliance within rounding.

[Native comparison figure](../../evidence/batch3/pto/paper-attempt/figure.png) · [Comparison report](../../evidence/batch3/pto/paper-attempt/report.json)
