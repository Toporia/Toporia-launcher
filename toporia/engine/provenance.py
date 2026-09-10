# engine/provenance.py — what produced a result, recorded next to it.
#
# Every run writes run.json into its output directory: the exact scenario and
# solver (in full, plus a short fingerprint of each), the software versions and
# git commit, and how the run ended.
#
# Two results with the same scenario fingerprint were solved on the same
# problem; two with the same solver fingerprint were solved the same way.  That
# is what makes a comparison reproducible and citable.

import functools
import platform
import subprocess
from datetime import datetime, timezone

import numpy as np
import scipy

import toporia
from toporia.core.run import PROJECT_ROOT
from toporia.core.serialize import fingerprint, to_dict


@functools.lru_cache(maxsize=1)
def _git_state():
    """Commit and dirty flag of the Toporia checkout, or None outside a git repo."""
    def git(*args):
        return subprocess.run(["git", "-C", str(PROJECT_ROOT), *args],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    try:
        return {
            "commit": git("rev-parse", "HEAD"),
            # Untracked files (such as results/) do not change what code ran.
            "dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        }
    except (OSError, subprocess.SubprocessError):
        return None


def software():
    """Versions of everything that can change a result."""
    return {
        "toporia": toporia.__version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "platform": platform.platform(),
        "git": _git_state(),
    }


def run_record(run, *, iterations, stop_reason, responses):
    """The provenance document written as run.json at the end of every run."""
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "software": software(),
        "scenario": {"fingerprint": fingerprint(run.scenario), "definition": to_dict(run.scenario)},
        "solver": {"fingerprint": fingerprint(run.solver), "definition": to_dict(run.solver)},
        "result": {"iterations": iterations, "stop_reason": stop_reason, "final": responses},
    }
