# harmonic: source comparison and remaining work

Functions: response:dynamic_compliance

Target: Ma-Kikuchi-Hagiwara (1993) frequency-response family: exact objective, numbered panel and loading pending; PolyDyna is a related transient method.

Status: paper_reproduction_to_fix. Independent checks passed within their reported scope.

Limits: Own real undamped amplitude response with SIMP/MMA, not the source's homogenization/MOC scheme or PolyDyna's HHT-alpha transient formulation. F-transpose-u is an amplitude quantity, not net work over a cycle. No resonance-crossing optimization or robust band objective is implemented here.

Next: Choose a genuinely frequency-domain undamped benchmark or implement a separate damped/transient formulation. PolyDyna's HHT-alpha time response is not the present amplitude equation.

[Figure](../../evidence/batch4/harmonic/figure.png) · [Report](../../evidence/batch4/harmonic/report.json) · [Math](../../evidence/batch4/harmonic/description.html)
