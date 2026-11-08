"""python -m toporia — same as the `toporia` command (see toporia/apps/cli.py)."""

from toporia.apps.cli import main

# Guarded: parallel runs start worker processes that import this module again (Windows).
if __name__ == "__main__":
    raise SystemExit(main())
