# Convergence-triggered beta: unresolved research comparison

Target: Convergence-triggered continuation described in section 4; exact design history unavailable.

Numerical issue: **resolved** (28 October 2026). The trigger watched design-variable change, which never settles under a sharp projection, so it always fell back to max_every; it now watches the physical density and reaches beta 128 at iteration 116. On MMA with move 0.1 the companion converges at iteration 121 with compliance 189.10.

Reason: The synthetic change signal and minimum-duration guard are declared Toporia choices. The source paper's actual observed design history is not reconstructed.

Numerical checks: True. A passing engineering check is not a paper reproduction.

Next: Recover actual paper design-change observations and trigger settings; synthetic rule agreement and an unconverged OC companion are insufficient.

[Figure and numerical report](../../evidence/batch2/schedule_settled/report.json) · [Generated figure](../../evidence/batch2/schedule_settled/figure.png)
