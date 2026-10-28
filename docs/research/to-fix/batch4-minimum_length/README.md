# minimum_length: source comparison and remaining work

Functions: response:minimum_length

Target: Zhou/Dunning length constraints: exact source panel and projection conventions pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: Own physical-field/KS variant is not the original three-field formulation. Gray fields, boundary stencils and mesh resolution prevent a universal minimum-feature certificate. In this bounded 24 x 8 example both length constraints remain violated and the field stays grey: on a grey field every cell violates the indicator (about 3800 times its tolerance at the uniform start), so MMA barely moves. With a Heaviside projection sharpened to beta 32 and the tolerance tightened from 100 to 1 on a 180 x 60 mm MBB (60 x 20 cells, mmapy MMA), the field becomes black and white, but 1-cell members and holes remain and the indicators stay about 5 times their tolerance; pyMOTO MMA's subproblem then takes about 30 s per step. The function does not yet show its intended behaviour; its edge stencils and KS calibration need checking against Zhou et al.

Next: Align the original three-field source example, or keep the current nodal-KS physical-field variant separate. Resolve the cone adequately and calibrate curved/diagonal features.

[Figure](../../evidence/batch4/minimum_length/figure.png) · [Report](../../evidence/batch4/minimum_length/report.json) · [Math](../../evidence/batch4/minimum_length/description.html)
