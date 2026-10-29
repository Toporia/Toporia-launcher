# minimum_length: source comparison and remaining work

Functions: response:minimum_length

Target: Zhou/Dunning length constraints: exact source panel and projection conventions pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: Own physical-field/KS variant, not the original three-field formulation; mesh resolution and grey fields prevent a universal minimum-size certificate. Until 29 October 2026 the indicator penalised every cone average below 1 instead of below the threshold: the inside corners of every junction then violated it, so even a truss of wide members was infeasible and the optimiser kept 1-cell members. The constraints are switched in gradually (tolerance 64 times larger at the start, halved every 40 steps) while a projection sharpens to beta 16 (doubled every 60), as in Zhou et al.; started at full strength on a grey field every cell violates and MMA barely moves. The medial-line detector uses a decay of 0.3 times (R/h)^4: at 1 a short thin member between two solid regions escaped, because the average rises along it. Without the constraints the same problem keeps members 1-2 mm wide.

Next: Align the original three-field source example, or keep the current nodal-KS physical-field variant separate. Resolve the cone adequately and calibrate curved/diagonal features.

[Figure](../../evidence/batch4/minimum_length/figure.png) · [Report](../../evidence/batch4/minimum_length/report.json) · [Math](../../evidence/batch4/minimum_length/description.html)
