"""test_cli.py — the headless command line.

This is the architecture's acceptance test: every capability is reachable
without the GUI, starting from plain files.
"""

import json

import matplotlib
import pytest

matplotlib.use("Agg")   # sweeps and comparisons draw figures; never open a window

from toporia.apps.cli import main  # noqa: E402
from toporia.framework import Solver  # noqa: E402
from toporia.framework.problem.files import fingerprint, load, save  # noqa: E402

# Small and fast: every command below runs real optimisations.
SMALL = ["--set", "m=0.25", "--set", "max_iter=3", "--set", "tol=0", "--set", "save_every=0"]


def test_list_shows_every_registry(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "MBB Beam" in out and "density_mma" in out and "heaviside" in out


def test_export_then_run_from_the_files(tmp_path):
    assert main(["export", "MBB Beam", str(tmp_path)]) == 0
    scenario_file = tmp_path / "mbb_beam.scenario.json"
    solver_file = tmp_path / "mbb_beam.solver.json"

    out = tmp_path / "out"
    assert main(["run", str(scenario_file), str(solver_file), "--out", str(out), *SMALL]) == 0
    record = json.loads((out / "run.json").read_text())
    assert record["scenario"]["fingerprint"] == fingerprint(load(scenario_file))
    assert record["result"]["iterations"] == 3
    assert (out / "final_density.png").exists()


def test_run_a_preset_with_overrides(tmp_path):
    assert main(["run", "Cantilever", "--out", str(tmp_path), *SMALL,
                 "--set", "method=density_mma", "--set", "interpolation.penal=4"]) == 0
    solver = json.loads((tmp_path / "run.json").read_text())["solver"]["definition"]
    assert solver["method"] == "density_mma"
    assert solver["interpolation"] == {"type": "simp", "penal": 4}


def test_compare_two_solvers_on_one_scenario(tmp_path):
    oc = save(Solver(method="density"), tmp_path / "oc.solver.json")
    mma = save(Solver(method="density_mma"), tmp_path / "mma.solver.json")
    assert main(["compare", "MBB Beam", str(oc), str(mma), "--out", str(tmp_path), *SMALL]) == 0
    assert (tmp_path / "compare_oc_vs_mma" / "comparison.png").exists()


def test_sweep(tmp_path):
    assert main(["sweep", "MBB Beam", "--param", "volfrac", "--range", "0.3", "0.5",
                 "--grid", "1", "2", "--out", str(tmp_path), *SMALL]) == 0
    assert (tmp_path / "sweep_volfrac" / "sweep_grid.png").exists()


def test_an_unknown_scenario_is_a_clear_error():
    with pytest.raises(SystemExit, match="neither a scenario file nor a preset"):
        main(["run", "No Such Problem"])


def test_check_reports_each_plugin_and_fails_on_an_unknown_one(capsys):
    assert main(["check", "filter:symmetry", "response:volume"]) == 0
    out = capsys.readouterr().out
    assert "filter SymmetryFilter (symmetry): conforms" in out and "2 of 2 conform" in out
    with pytest.raises(ValueError, match="Unknown filter"):
        main(["check", "filter:nope"])


def test_benchmark_runs_methods_on_problems_and_writes_one_table(tmp_path, capsys):
    assert main(["benchmark", "--methods", "q4+oc", "q4+mma", "--problems", "MBB Beam",
                 "--set", "m=0.3", "--set", "max_iter=3", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "benchmark.csv").exists()
    assert "referee_compliance" in capsys.readouterr().out
