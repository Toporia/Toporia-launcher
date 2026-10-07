"""conftest.py — makes the repository root importable during tests.

Without this, `from tests.golden._harness import run_case` only resolves when pytest
happens to be invoked from the repo root.  Adding it explicitly means the suite
runs the same way from any working directory, and from an IDE test runner.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
