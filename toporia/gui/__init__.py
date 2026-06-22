# This file marks the gui/ folder as a Python *package* — without it,
# "from gui import launch" would fail because Python wouldn't treat the
# folder as an importable unit.
#
# It also defines what is publicly available when someone writes
# "from gui import ...".  Here we just re-export the launch function
# so the top-level gui.py only needs one import line.

from .app import launch   # the dot means "from the same package (gui/)"

__all__ = ["launch"]      # explicit list of public names
