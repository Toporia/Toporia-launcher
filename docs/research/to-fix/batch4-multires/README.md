# multires: source comparison and remaining work

Functions: model:q4_multiresolution, physics:q4_multiresolution

Target: Nguyen et al. MTOP examples: exact source panel and design/analysis grids pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: This exact-subcell Galerkin variant differs from the source centroid rule.

Numerical issue: **resolved** (28 October 2026). The recorded fine-Q4 discrepancy (ratio 0.298) came from a filter smaller than one analysis cell; the model now refuses that, and the showcase's coarse/fine ratio is 0.986, with a fine-Q4 compliance equal to plain Q4's.

Next: Align the source's three grids/projection and centroid integration, or identify this Galerkin variant separately.

[Figure](../../evidence/batch4/multires/figure.png) · [Report](../../evidence/batch4/multires/report.json) · [Math](../../evidence/batch4/multires/description.html)
