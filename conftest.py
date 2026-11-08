"""conftest.py — makes the repository root importable during tests.

Without this, `from tests.golden._harness import run_case` only resolves when pytest
happens to be invoked from the repo root.  Adding it explicitly means the suite
runs the same way from any working directory, and from an IDE test runner.

Set TOPORIA_EXIT_TRACE=<seconds> to find what keeps a finished run from exiting:
after the summary the threads still alive are listed, and if the process is still
there that many seconds later, every thread's stack is printed (repeatedly).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Grids run one cell after another in the tests (fast for tiny runs, and the same results);
# tests/engine/test_modes.py checks the parallel path itself.
os.environ.setdefault("TOPORIA_WORKERS", "1")


def pytest_unconfigure(config):
    delay = os.environ.get("TOPORIA_EXIT_TRACE")
    if not delay:
        return
    import faulthandler
    import threading

    alive = [t for t in threading.enumerate() if t is not threading.main_thread()]
    print(f"\n[exit trace] threads alive after the summary: {len(alive)}", file=sys.stderr)
    for thread in alive:
        print(f"[exit trace]   {thread.name!r} daemon={thread.daemon}", file=sys.stderr)
    faulthandler.dump_traceback_later(float(delay), repeat=True, file=sys.stderr)
