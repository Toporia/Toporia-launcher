"""The original PTOc reproduces the authors' code; the pto variant stays a separate method."""

import json
from pathlib import Path

import numpy as np
import pytest

from toporia.engine.loop import initialized_method, run_single_with_store
from toporia.plugins.problems import get_run
from toporia.plugins.updaters.ptoc import ptoc_kernel

REFERENCE = Path(__file__).resolve().parents[1] / "references/paper_ptoc.json"


def test_ptoc_reproduces_the_author_code_on_figure_3(tmp_path):
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    store, density = run_single_with_store(get_run("Paper: PTOc Fig. 3 (MBB)").with_output_dir(tmp_path))
    printed = np.array([row[2] for row in reference["history"]])
    ours = np.array(store.objectives)
    # The author prints one more line: termination is tested before the update.
    assert len(ours) == reference["iterations"] - 1
    assert np.all(np.abs(np.round(ours, 2) - printed[:len(ours)]) <= 0.0051)
    assert np.max(np.abs(density - np.flipud(np.array(reference["density"])))) < 1e-6


def test_ptoc_kernel_is_the_linear_cone():
    kernel = ptoc_kernel(1.5, 2)
    assert kernel.shape == (3, 3)
    assert kernel[1, 1] == pytest.approx(1.5) and kernel[0, 1] == pytest.approx(0.5)
    assert kernel[0, 0] == pytest.approx(1.5 - np.sqrt(2.0))


def test_ptoc_refuses_a_filter_chain():
    run = get_run("Paper: PTOc Fig. 3 (MBB)").updated(filter_specs=[{"type": "density"}], m=0.2)
    with pytest.raises(ValueError, match="filter chain"):
        initialized_method(run)
