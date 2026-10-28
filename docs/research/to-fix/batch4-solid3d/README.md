# solid3d: source comparison and remaining work

Functions: model:h8, physics:h8_solid

Target: Liu-Tovar top3d reference; small 12x4x2 author-code benchmark, not an identified paper panel.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: The GUI companion uses production trapezoidal depth-load quadrature. The native scalar probe explicitly substitutes uniform nodal depth shares. No native final-field or paper-image equality is claimed.

Next: Recover a numbered top3d paper panel; align discrete depth loads before any full-field comparison. Keep the 39-step scalar oracle scope separate from the production companion.

[Figure](../../evidence/batch4/solid3d/figure.png) · [Report](../../evidence/batch4/solid3d/report.json) · [Math](../../evidence/batch4/solid3d/description.html)
