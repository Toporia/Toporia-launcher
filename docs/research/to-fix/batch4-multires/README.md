# multires: source comparison and remaining work

Functions: model:q4_multiresolution, physics:q4_multiresolution

Target: Nguyen et al. MTOP examples: exact source panel and design/analysis grids pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: This exact-subcell Galerkin variant differs from the source centroid rule. Fine features can be artificially stiff on the coarse analysis grid.

Next: Align the source's three grids/projection and centroid integration or identify this Galerkin variant separately. Investigate the recorded fine-Q4 stiffness discrepancy before ranking designs.

[Figure](../../evidence/batch4/multires/figure.png) · [Report](../../evidence/batch4/multires/report.json) · [Math](../../evidence/batch4/multires/description.html)
