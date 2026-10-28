# Volume-preserving projection: unresolved research comparison

Target: Ferrari-Sigmund (2020) volume-preserving construction; exact source figure remains to select.

Numerical issue: **resolved** (28 October 2026). The zero threshold-derivative
denominator at 0/1 designs now has its exact treatment: the identity for
all-solid/all-void designs (checked by one-sided finite differences), an explicit
error for mixed 0/1 designs, which have no gradient. See the header of
[`heaviside.py`](../../../../toporia/plugins/filters/heaviside.py).

Reason the comparison stays open: mean preservation does not make every cell or
optimized topology agree with top99neo. The input field here is a controlled
ramp, not a paper design.

Numerical checks: True. A passing engineering check is not a paper reproduction.

Next: align a numbered top99neo source figure and compare its threshold history.

[Figure and numerical report](../../evidence/batch2/heaviside_volume/report.json) · [Generated figure](../../evidence/batch2/heaviside_volume/figure.png)
