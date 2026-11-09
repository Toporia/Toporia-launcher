"""test_choice_sweeps.py — sweeping a choice of part (optimiser, model, material law, ...).

A sweep variable can be a choice of part with a few options instead of a numeric range:
the updater, the physics model, the whole method, the material law, the representation or
a filter's type.  Each option replaces only that part; a combination that cannot run is
not run and its cell says why; a choice can stand against a numeric parameter in a 2-D
sweep; the command line takes --values; the GUI panels list the options and save them.
"""

import os
from pathlib import Path

import pytest

from toporia_core.engine.modes.choices import apply_choice, assign, problems
from toporia_core.engine.modes.sweep import sweep, sweep_2d
from toporia_library.problems import get_run


def _run(tmp_path, **values):
    return get_run("MBB Beam").updated(max_iter=3, tol=0.0, save_every=0, m=0.4, **values).with_output_dir(tmp_path)


def test_a_choice_replaces_only_its_part(tmp_path):
    run = _run(tmp_path, method="q4+oc")
    assert apply_choice(run, "choice:updater", "mma").solver.method == "q4+mma"
    assert apply_choice(run, "choice:model", "q4_multiresolution").solver.method == "q4_multiresolution+oc"
    assert apply_choice(run, "choice:method", "levelset").solver.method == "levelset"
    assert apply_choice(run, "choice:interpolation", "ramp").solver.interpolation == {"type": "ramp"}
    assert apply_choice(run, "choice:representation", "mmc").solver.representation == {"type": "mmc"}
    assert apply_choice(run, "choice:filters[0]", "sensitivity").solver.filter_specs[0] == {"type": "sensitivity"}
    assert assign(run, "volfrac", 0.3).scenario.volfrac == 0.3                    # numeric paths still work
    with pytest.raises(ValueError, match="no filter 3"):
        apply_choice(run, "choice:filters[2]", "density")
    with pytest.raises(ValueError, match="whole method"):
        apply_choice(apply_choice(run, "choice:method", "levelset"), "choice:updater", "oc")


def test_a_combination_that_cannot_run_says_why(tmp_path):
    run = _run(tmp_path, method="q4+oc")
    assert problems(apply_choice(run, "choice:updater", "mma")) == []
    assert "Unknown updater" in problems(apply_choice(run, "choice:updater", "not_an_updater"))[0]
    oc_with_bars = apply_choice(run, "choice:representation", "mmc")
    assert problems(oc_with_bars)                                                 # OC needs element densities
    assert "no material law" in problems(apply_choice(run, "choice:interpolation", "nope"))[0]


def test_a_sweep_over_updaters_runs_the_ones_that_can(tmp_path, monkeypatch):
    monkeypatch.setenv("TOPORIA_WORKERS", "1")
    grid = sweep("choice:updater", 0, 0, 1, 3, _run(tmp_path), values=["oc", "mma", "not_an_updater"])
    folder = tmp_path / "sweep_updater"
    assert (folder / "updater_oc" / "final_density.png").exists()
    assert (folder / "updater_mma" / "final_density.png").exists()
    assert not (folder / "updater_not_an_updater").exists()
    assert grid is None or Path(grid).exists()


def test_a_choice_against_a_parameter_in_2d(tmp_path, monkeypatch):
    monkeypatch.setenv("TOPORIA_WORKERS", "1")
    sweep_2d("choice:interpolation", 0, 0, 0, "volfrac", 0.3, 0.5, 2, _run(tmp_path),
             row_values=["simp", "ramp"])
    folder = tmp_path / "sweep2d_interpolation_vs_volfrac"
    made = sorted(p.name for p in folder.iterdir() if p.is_dir())
    assert made == ["interpolation_ramp__volfrac_0.3", "interpolation_ramp__volfrac_0.5",
                    "interpolation_simp__volfrac_0.3", "interpolation_simp__volfrac_0.5"]


def test_a_choice_needs_its_options(tmp_path):
    with pytest.raises(ValueError, match="give its options"):
        sweep("choice:updater", 0, 1, 1, 2, _run(tmp_path))


def test_the_command_line_takes_values(tmp_path, monkeypatch):
    monkeypatch.setenv("TOPORIA_WORKERS", "1")
    from toporia_core.cli import main
    code = main(["sweep", "MBB Beam", "--param", "choice:updater", "--values", "oc", "mma",
                 "--set", "max_iter=2", "--set", "m=0.4", "--out", str(tmp_path)])
    assert code == 0 and (tmp_path / "sweep_updater" / "updater_mma").exists()


def test_the_gui_panels_list_the_options_and_save_them():
    pytest.importorskip("PySide6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from toporia_gui.panels.modes import Sweep2DParamsGroup, SweepParamsGroup
    group = SweepParamsGroup()
    group.refresh([("Vol fraction", "volfrac"), ("Filter 1 · Radius", "filters[0].rmin")])
    paths = [group.param.itemData(i) for i in range(group.param.count())]
    assert {"choice:updater", "choice:model", "choice:filters[0]"} <= set(paths)
    assert group.options.isHidden()
    group.param.setCurrentIndex(paths.index("choice:updater"))
    assert not group.options.isHidden() and group.min_val.isHidden()
    for i in range(group.options.count()):
        if group.options.item(i).data(Qt.UserRole) in ("oc", "mma"):
            group.options.item(i).setCheckState(Qt.Checked)
    assert group.selected() == {"values": ["oc", "mma"]}
    group.options.show_choice("choice:updater", keep=[])
    group.set_selected({"values": ["mma"]})
    assert group.selected() == {"values": ["mma"]}

    grid = Sweep2DParamsGroup()
    grid.refresh([("Vol fraction", "volfrac"), ("Mesh", "m")])
    rows = [grid.row_param.itemData(i) for i in range(grid.row_param.count())]
    grid.row_param.setCurrentIndex(rows.index("choice:interpolation"))
    grid.set_selected({"row_values": ["simp", "ramp"]})
    assert grid.selected() == {"row_values": ["simp", "ramp"], "col_values": None}
    assert grid.row_min.isHidden() and not grid.col_min.isHidden()
