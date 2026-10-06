"""test_modes_smoke.py — one smoke test per analysis mode.

These assert only that each mode runs end to end and produces its output file.
They deliberately do NOT check numbers: the golden tests in test_golden.py pin
the physics, and duplicating that here would just make the suite slow.

What these protect is the engine layer (toporia/functions/) — the sweep,
compare and sensitivity drivers that the GUI calls.  Phase 1 moves this code
into engine/; these tests are how you know the move was clean.

Configs are tiny on purpose: several of these modes run four or more full
optimisations each.
"""

from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")   # never open a window during tests

from toporia.engine.modes.compare import compare_load_cases, compare_two  # noqa: E402
from toporia.engine.modes.sensitivity import (  # noqa: E402
    sensitivity_field,
    sensitivity_sweep,
    sensitivity_sweep_2d,
)
from toporia.engine.modes.single import run_one  # noqa: E402
from toporia.engine.modes.sweep import sweep, sweep_2d  # noqa: E402
from toporia.framework import LoadCase  # noqa: E402
from toporia.plugins.problems import get_run  # noqa: E402


@pytest.fixture
def cfg(tmp_path):
    """The smallest configuration that still exercises the full pipeline."""
    return get_run("MBB Beam").updated(m=0.25, max_iter=3, tol=0.0, save_every=0).with_output_dir(tmp_path)


def _assert_output(path):
    path = Path(path)
    assert path.exists(), f"expected output file was not written: {path}"
    assert path.stat().st_size > 0, f"output file is empty: {path}"


def test_run_one(cfg):
    store, density = run_one(cfg)
    assert density.shape == (5, 15)
    _assert_output(Path(cfg.output.dir) / "final_density.png")
    _assert_output(Path(cfg.output.dir) / "final_density.csv")


def test_run_one_fires_iteration_callback(cfg):
    """The GUI's live canvas depends on this callback; pin its contract."""
    seen = []
    run_one(cfg, on_iteration=lambda d, objectives, it: seen.append((d.shape, it)))
    assert len(seen) == cfg.solver.max_iter
    assert [it for _, it in seen] == list(range(1, cfg.solver.max_iter + 1))


def test_sweep(cfg):
    sweep("volfrac", 0.3, 0.5, 1, 2, cfg)
    _assert_output(Path(cfg.output.dir) / "sweep_volfrac" / "sweep_grid.png")


def test_sweep_2d(cfg):
    sweep_2d("volfrac", 0.3, 0.5, 1, "method.penal", 2.0, 3.0, 2, cfg)
    _assert_output(Path(cfg.output.dir) / "sweep2d_volfrac_vs_method.penal" / "sweep2d_grid.png")


def test_compare_two(cfg):
    img, a, b = compare_two("volfrac", 0.3, 0.5, cfg)
    _assert_output(img)
    assert a.shape == b.shape


def test_compare_load_cases(cfg):
    img, a, b = compare_load_cases(
        [LoadCase(Fmag=1.0, Fa=270.0, weight=1.0)],
        [LoadCase(Fmag=1.0, Fa=0.0,   weight=1.0)],
        cfg,
    )
    _assert_output(img)
    assert a.shape == b.shape


def test_sensitivity(cfg):
    img, sens = sensitivity_field("volfrac", 0.4, 0.05, cfg)
    _assert_output(img)
    assert sens.shape == (5, 15)


def test_sensitivity_sweep(cfg):
    grid = sensitivity_sweep("method.penal", 2.0, 3.0, 1, 2, "volfrac", 0.4, 0.05, cfg)
    _assert_output(grid)


def test_sensitivity_sweep_2d(cfg):
    grid = sensitivity_sweep_2d("method.penal", 2.0, 3.0, 1, "filters[0].rmin", 1.5, 2.0, 2,
                                "volfrac", 0.4, 0.05, cfg)
    _assert_output(grid)
