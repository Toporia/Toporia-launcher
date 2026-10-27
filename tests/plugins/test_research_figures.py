"""Check paper recipes against independent author fields, not internal baselines."""

import json

import numpy as np
import pytest

from experiments.research_figures import FIXTURE, PRESETS, compare, solve
from experiments.research_inventory import inventory
from toporia.plugins.problems import get_run, problem_description


@pytest.mark.parametrize("kind", PRESETS)
def test_paper_panel_reproduction(kind):
    reference = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = solve(kind)
    comparison = compare(result, reference["cases"][kind])
    assert comparison["native_code_match"], comparison
    assert result["stop_reason"] == "tolerance"
    assert result["physical_volume_fraction"] <= .5001
    assert np.isfinite(result["fresh_final_compliance"])


def test_changed_field_cannot_pass_reproduction():
    reference = {"iterations": 1, "density": [[.5]], "history": [[1, 200., .5, .005]]}
    assert compare(reference, reference)["native_code_match"]
    altered = {**reference, "density": [[.6]]}
    assert not compare(altered, reference)["native_code_match"]


def test_coordinate_conversion_is_explicit_and_only_vertical():
    reference = {"iterations": 1, "density": [[.2, .4], [.6, .8]], "history": [[1, 200., .5, .005]]}
    actual = {**reference, "density": [[.6, .8], [.2, .4]]}
    assert compare(actual, reference)["native_code_match"]
    mirrored = {**actual, "density": [[.8, .6], [.4, .2]]}
    assert not compare(mirrored, reference)["native_code_match"]


def test_preset_pins_paper_settings_and_carries_science():
    for kind, name in PRESETS.items():
        run = get_run(name)
        assert run.solver.filter_specs == [{"type": kind, "rmin": 2.4}]
        assert run.solver.interpolation == {"type": "simp", "penal": 3.}
        assert run.solver.max_iter == 200 and run.solver.tol == .01
        assert run.scenario.Lx == 60 and run.scenario.Ly == 20
        description = problem_description(name)
        assert description.equations and description.symbols and description.limitations
        assert "3(a)" in description.figure
        assert f"filter:{kind}" in description.functions
    # Adding a research recipe must not silently change the general benchmark.
    assert get_run("MBB Beam").solver.filter_specs == [{"type": "density"}]


def test_inventory_covers_discovered_implementations_and_preset_links():
    report = inventory()
    ids = [row["id"] for row in report["functions"]]
    assert len(ids) == len(set(ids))
    assert not report["discovery_errors"]
    assert "physics:q4_plane_stress" in ids
    assert "filter:density" in ids
    for preset in report["presets"]:
        assert set(preset["functions"]) <= set(ids)
