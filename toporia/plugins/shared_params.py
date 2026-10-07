# plugins/shared_params.py — parameters declared once and used by more than one plugin.
#
# A parameter shown under the same name in two plugins must mean the same thing
# and have the same range, so it is declared here once:
#
#   PENAL  the SIMP penalty, used by the Q4 engine and the pyMOTO model
#   MOVE   the move limit, used by OC, MMA and pyMOTO's MMA and GCMMA
#   RMIN   the filter radius, used by the density and sensitivity filters
#          and by the pyMOTO model's own density filter

from toporia.framework.params import Param

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

RMIN = Param(
    "rmin", 1.5, "Radius",
    "Filter radius in elements. Sets the minimum member size and suppresses checkerboarding.",
    min=0.5, max=20.0, step=0.5, decimals=2, units="el",
)
