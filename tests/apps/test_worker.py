"""Run actual headless worker processes and verify durable, isolated results."""

import json
import subprocess
import sys

import numpy as np
import pytest

from toporia.apps.gui.geometry import make_object
from toporia.apps.gui.project import Project
from toporia.framework.problem.run import Run
from toporia.framework.problem.scenario import Scenario
from toporia.framework.problem.solver import Solver


def snapshot(folder, objects=None):
    if objects is None:
        objects = [make_object("line", (0, 0, 0), (0, 5, 0)),
                   make_object(position=(10, 2, 0), role="load", force=[0, -2, 0])]
    run = Run(scenario=Scenario(Lx=10, Ly=5, regions=objects), solver=Solver(max_iter=3, filter_specs=[{"type": "density"}]))
    return Project("Worker test", run, objects=objects).save(folder / "input.top")


@pytest.mark.parametrize("mode,kind", [("Run One", "density"), ("Sweep", "image"), ("Compare Two", "image")])
def test_worker_uses_saved_settings_and_writes_result_and_status(tmp_path, mode, kind):
    path = snapshot(tmp_path)
    project = Project.load(path)
    project.study = {"mode": mode,
                     "sg": {"param": "volfrac", "min_val": .3, "max_val": .5, "n_rows": 1, "n_cols": 2},
                     "cg": {"param": "volfrac", "value_a": .3, "value_b": .5}}
    project.save()
    result = subprocess.run([sys.executable, "-m", "toporia.apps.gui_worker", str(path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    events = [json.loads(line[8:]) for line in result.stdout.splitlines() if line.startswith("TOPORIA ")]
    assert any(event["event"] == "iteration" for event in events)
    status = json.loads((tmp_path / "session.json").read_text())
    assert status["status"] == "finished"
    assert status["result"]["kind"] == kind
    assert Project.load(path).study == project.study
    if kind == "density":
        density = np.load(tmp_path / "design.npy")
        assert density.shape == (5, 10) and np.isfinite(density).all()


def test_worker_reports_invalid_problem_and_cooperative_stop_distinctly(tmp_path):
    invalid = tmp_path / "invalid"
    path = snapshot(invalid, [])
    result = subprocess.run([sys.executable, "-m", "toporia.apps.gui_worker", str(path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    assert json.loads((invalid / "session.json").read_text())["status"] == "error"
    stopped = tmp_path / "stopped"
    path = snapshot(stopped)
    (stopped / "stop.flag").touch()
    result = subprocess.run([sys.executable, "-m", "toporia.apps.gui_worker", str(path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert json.loads((stopped / "session.json").read_text())["status"] == "stopped"
    assert not (stopped / "design.npy").exists()
