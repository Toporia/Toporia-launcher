# _shared_params.py — Param declarations used by more than one method.
#
# Private module (leading underscore), so the method registry does not scan it.
# Phase 4 folds the SIMP methods into one shared model; until then this keeps a
# single definition of the parameters they have in common.

from toporia.core.params import Param

PENAL = Param(
    "penal", 3.0, "Penalty p",
    "SIMP penalty exponent. Higher values push intermediate densities toward solid or void.",
    min=1.0, max=10.0, step=0.5, decimals=1,
)

MOVE = Param(
    "move", 0.2, "Move limit",
    "Largest change of any element's density in a single update.",
    min=0.01, max=1.0, step=0.05, decimals=2,
)
