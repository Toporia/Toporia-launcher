# buckling: source comparison and remaining work

Functions: model:q4_buckling, physics:q4_buckling, response:buckling_load

Target: Ferrari-Sigmund-Guest column examples: exact paper panel and source settings pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: Toporia uses an inverse-factor p-norm rather than the source's KS aggregation, plus own column geometry/interpolation. It is not a direct topBuck250 port. Linear buckling omits postbuckling and imperfections.

Next: Align source pre-stress interpolation and KS aggregation rather than assuming the inverse-factor p-norm is topBuck250. Recover a numbered design beyond the independent Euler column.

[Figure](../../evidence/batch4/buckling/figure.png) · [Report](../../evidence/batch4/buckling/report.json) · [Math](../../evidence/batch4/buckling/description.html)
