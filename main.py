"""
main.py — launch the Toporia desktop app.

Usage:
    python main.py [--project FILE.top] [--smoke-test]

The same entry point is the bundled Windows program (toporia/apps/desktop.py).
"""

from toporia.apps.desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
