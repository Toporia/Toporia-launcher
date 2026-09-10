# _common.py — Param declarations shared by more than one updater.
#
# Private module (leading underscore), so the updater registry does not scan it.

from toporia.core.params import Param

MOVE = Param(
    "move", 0.2, "Move limit",
    "Largest change of any element's density in a single update.",
    min=0.01, max=1.0, step=0.05, decimals=2,
)
