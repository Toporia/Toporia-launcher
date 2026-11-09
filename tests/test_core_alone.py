"""The core runs without matplotlib and Pillow (the split follow-up).

toporia_core writes its PNGs itself (engine/png.py) and draws figures only when matplotlib
is there (engine/plotting.py).  A fresh interpreter in which matplotlib and PIL cannot be
imported runs a single optimisation and a sweep through the core and still writes every
number, CSV and density image; only the matplotlib figures are skipped, with a notice.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np

from toporia_core.engine.png import read_png, write_png

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = textwrap.dedent('''
    import importlib.abc, sys

    class Blocked(importlib.abc.MetaPathFinder):
        """matplotlib and PIL are not installed here, as far as anything can tell."""
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("matplotlib", "PIL"):
                raise ModuleNotFoundError(f"No module named {name!r} (blocked)")
            return None

    sys.meta_path.insert(0, Blocked())
    import importlib.util
    importlib.util.find_spec = (lambda real: (lambda name, *a: None if name.split(".")[0] in
                                ("matplotlib", "PIL") else real(name, *a)))(importlib.util.find_spec)

    from pathlib import Path
    from toporia_core.engine.loop import run_single
    from toporia_core.engine.modes.sweep import sweep
    from toporia_core.framework.problem.presets import get_run

    out = Path(sys.argv[1])
    run = get_run("MBB Beam").updated(max_iter=3, tol=0.0, save_every=0, m=0.5)
    run_single(run.with_output_dir(out / "single"))
    assert (out / "single" / "run.json").exists() and (out / "single" / "final_density.png").exists()
    grid = sweep("volfrac", 0.4, 0.5, 1, 2, run.with_output_dir(out / "sweep"))
    assert grid is None                      # the figure needs matplotlib; the runs are there
    assert "matplotlib" not in sys.modules and "PIL" not in sys.modules
    print("core alone: ok")
''')


def test_png_round_trip_without_an_imaging_library(tmp_path):
    grey = (np.arange(12 * 7) % 256).astype(np.uint8).reshape(7, 12)
    colour = np.stack([grey, 255 - grey, grey // 2], axis=-1)
    for name, pixels in (("grey.png", grey), ("colour.png", colour)):
        write_png(tmp_path / name, pixels)
        assert np.array_equal(read_png(tmp_path / name), pixels)


def test_the_core_runs_without_matplotlib_and_pillow(tmp_path):
    result = subprocess.run([sys.executable, "-c", SCRIPT, str(tmp_path)], capture_output=True, text=True,
                            cwd=ROOT, timeout=600, env={**__import__("os").environ, "TOPORIA_WORKERS": "1"})
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-3000:]
    assert "core alone: ok" in result.stdout
    assert "figures skipped" in result.stdout
