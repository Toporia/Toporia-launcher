"""The engine loop stops on a non-finite design instead of running on to its cap."""

import numpy as np
import pytest

from toporia.engine.loop import run_single
from toporia.plugins.problems import get_run
from toporia.plugins.updaters.oc import OCUpdater


def test_a_non_finite_design_stops_the_run_with_its_iteration(monkeypatch, tmp_path):
    def broken(self, x, evaluation, completed):
        return np.full_like(x, np.nan)
    monkeypatch.setattr(OCUpdater, "update", broken)
    run = get_run("MBB Beam").updated(m=0.3, max_iter=20, save_every=0).with_output_dir(tmp_path)
    with pytest.raises(FloatingPointError, match="iteration 1:"):
        run_single(run)
