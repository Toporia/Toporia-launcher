# toporia_gui/__init__.py — the desktop app as a package.
#
# launch() starts the app.  The core finds it through the entry point "toporia.apps",
# name "gui" (pyproject.toml), so `toporia` with no command opens it without the core
# importing this package by name.  Qt is loaded only inside launch(): the headless worker
# (worker.py) imports the project modules without starting a GUI.

from toporia_core import __version__ as GUI_VERSION  # one version for the program and its GUI


def launch(project_path=None):
    """Load Qt only when launching; headless workers may use project documents."""
    from .app import launch as start
    return start(project_path)

__all__ = ["GUI_VERSION", "launch"]      # explicit list of public names
