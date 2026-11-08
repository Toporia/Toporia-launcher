"""python -m toporia_core — same as the `toporia` command (see toporia_core/cli.py)."""

from toporia_core.cli import main

# Guarded: parallel runs start worker processes that import this module again (Windows).
if __name__ == "__main__":
    raise SystemExit(main())
