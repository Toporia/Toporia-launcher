# Ordered SIMP: formula audit: unresolved research comparison

Target: da Silveira-Palma (2022), Figure 1 modified curves, Table 1; compare original equations (2)-(3) separately.

Known execution issue: None observed in the recorded checks.

Reason: This verifies stiffness interpolation only, with 1e-8 absolute tolerance for the finite soft phase. No cost interpolation, non-monotone moduli, optimizer trajectory or paper bridge design is claimed.

Numerical checks: True. A passing engineering check is not a paper reproduction.

Next: Current attribution is corrected to the 2022 modified law. Reproducing the distinct original 2017 formula would need a separately declared variant, not an undocumented algorithm change.

[Figure and numerical report](../../evidence/batch2/ordered_simp/report.json) · [Generated figure](../../evidence/batch2/ordered_simp/figure.png)
