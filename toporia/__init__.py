"""
Toporia — open-source topology optimisation platform.

Quickstart
----------
    from toporia.plugins.problems import get_run
    from toporia.engine.loop import run_single

    run = get_run("MBB Beam").updated(volfrac=0.4)
    density = run_single(run)

Or from the command line:
    toporia run "MBB Beam" --set volfrac=0.4
    toporia                      (no command: launches the GUI, as does python main.py)
"""

__version__ = "0.1.0"
__author__  = "Toporia contributors"
