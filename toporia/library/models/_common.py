# _common.py — Param declarations shared by more than one model.
#
# Private module (leading underscore), so the model registry does not scan it.

from toporia.core.params import Param

PENAL = Param(
    "penal", 3.0, "Penalty p",
    "SIMP penalty exponent. Higher values push intermediate densities toward solid or void.",
    min=1.0, max=10.0, step=0.5, decimals=1,
)
