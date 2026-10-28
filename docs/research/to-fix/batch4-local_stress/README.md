# local_stress: source comparison and remaining work

Functions: response:local_stress

Target: PolyStress local-stress example: source polygonal mesh/relaxation/panel pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: The Q4 density-relaxed variant is not a PolyStress port. Finite penalties and a bounded solve do not certify local feasibility.

Next: Match PolyStress mesh, relaxation and AL update rules. Inspect exact relaxed peak and per-element feasibility rather than treating penalty reduction as success.

[Figure](../../evidence/batch4/local_stress/figure.png) · [Report](../../evidence/batch4/local_stress/report.json) · [Math](../../evidence/batch4/local_stress/description.html)
