"""
Toporia — open-source topology optimisation platform.

Quickstart
----------
    from toporia.library.problems import get_default_config
    from toporia.engine.runner import run_single

    cfg = get_default_config()          # MBB beam by default
    density = run_single(cfg)

Or launch the GUI:
    python main.py
"""

__version__ = "0.1.0"
__author__  = "Toporia contributors"
