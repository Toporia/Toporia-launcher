"""
main.py — launch the Morpho GUI.

Usage:
    python main.py
"""

import argparse

from toporia.apps.gui import launch

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Toporia project desktop")
    parser.add_argument("--project", help="Open a saved .top project")
    launch(parser.parse_args().project)
