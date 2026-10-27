# This file marks the gui/ folder as a Python *package* — without it,
# "from gui import launch" would fail because Python wouldn't treat the
# folder as an importable unit.
#
# It also defines what is publicly available when someone writes
# "from gui import ...".  Here we just re-export the launch function
# so the top-level gui.py only needs one import line.

GUI_VERSION = "0.2.1"


def launch(project_path=None):
    """Load Qt only when launching; headless workers may use project documents."""
    from .app import launch as start
    return start(project_path)

__all__ = ["launch"]      # explicit list of public names
