# multires: source comparison and remaining work

Functions: model:q4_multiresolution, physics:q4_multiresolution

Target: Nguyen et al. MTOP examples: exact source panel and design/analysis grids pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: This exact-subcell Galerkin variant differs from the source centroid rule. The coarse space is always slightly stiffer than fine Q4 (here 1.4%); features below one analysis cell would be much stiffer, so the model refuses smaller filter radii.

Next: Align the source's three grids/projection and centroid integration, or identify this Galerkin variant separately. The fine-Q4 stiffness discrepancy is resolved: filters below one analysis cell are refused (coarse/fine 0.986 here).

[Figure](../../evidence/batch4/multires/figure.png) · [Report](../../evidence/batch4/multires/report.json) · [Math](../../evidence/batch4/multires/description.html)
