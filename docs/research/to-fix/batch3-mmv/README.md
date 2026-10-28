# MMV superelliptical holes: unresolved paper comparison

Target: Zhang et al. (2017) 3D MMV: source geometry/panel incompatible with this restricted 2D variant.

Difference/gap: The source uses 3D B-spline void surfaces and DOF removal; this variant cannot reproduce them and cannot nucleate new holes.

Recorded execution: 59 steps; design change 0.009 < tol 0.01. Fresh final compliance 292.06097; physical fraction 0.49894902; budget 0.5; within budget +1e-4: True. Extra constraints within +1e-4: True. Finite/bounded execution does not establish feasibility, convergence or paper agreement.

Next: A 2017-source reproduction needs 3D B-spline void surfaces and DOF-removal support. Keep the 2D superellipse example explicitly separate until that algorithm is implemented.

[Figure](../../evidence/batch3/mmv/figure.png) · [Numerical report](../../evidence/batch3/mmv/report.json) · [Description and math](../../evidence/batch3/mmv/description.html)
