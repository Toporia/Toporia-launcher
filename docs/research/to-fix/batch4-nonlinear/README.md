# nonlinear: source comparison and remaining work

Functions: model:q4_nonlinear, physics:q4_nonlinear, response:end_compliance

Target: Wang et al./Buhl et al. nonlinear designs: matching source geometry, law and panel pending.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: The current void blend, material law, load pad and Newton controls are declared variant choices. A failed Newton solve must remain a failure, not an optimization result.

Next: Recover a numbered Buhl/Wang setup, constitutive law, load increments and void blending; compare full equilibrium/adjoint histories and retain Newton failures.

[Figure](../../evidence/batch4/nonlinear/figure.png) · [Report](../../evidence/batch4/nonlinear/report.json) · [Math](../../evidence/batch4/nonlinear/description.html)
