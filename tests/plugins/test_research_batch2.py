"""Research figures must expose numerical failures and unresolved paper targets."""

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.research_batch2 import CASES, CURVE_MATCHES, run_case
from experiments.research_figures import compare
from toporia.engine.loop import initialized_method
from toporia.framework.problem.run import Run
from toporia.plugins.problems import problem_description, problem_names
from toporia.plugins.problems._research_batch2 import QUARANTINED, description, metadata, recipe


@pytest.mark.parametrize("case_id", [name for name in CASES if name != "pde"])
def test_independent_equations_adjoints_and_honest_status(tmp_path, case_id):
    report = run_case(case_id, tmp_path)
    if case_id in QUARANTINED:
        assert report["quarantined_reason"]
        assert not report["checks"]["saturation_probe"]["all_solid_adjoint_finite"]
    else:
        assert report["checks"]["checks_passed"], report
    assert (tmp_path / case_id / "figure.png").is_file()
    if case_id in CURVE_MATCHES:
        assert report["paper_status"] == "source_equation_curve_match"
    else:
        assert report["paper_status"] == "paper_reproduction_to_fix"
        assert (tmp_path / case_id / "TO-FIX.md").is_file()
    assert report["paper_visual_status"] == "not_assessed"


@pytest.mark.parametrize("case_id", [case_id for case_id in CASES if case_id not in QUARANTINED])
def test_companion_preset_is_discovered_documented_and_executable(case_id):
    name = metadata(case_id)[0]
    assert name in problem_names()
    explanation = problem_description(name)
    assert explanation.equations
    assert explanation.functions == (CASES[case_id]["function"],)
    assert "GUI Run is an optimization companion" in explanation.setup
    scenario, solver = recipe(case_id)
    method = initialized_method(Run(scenario, solver))
    try:
        method.step(1)
        assert np.isfinite(method.get_responses()["objective"])
        assert np.all(np.isfinite(method.get_density()))
    finally:
        method.close()


def test_recorded_pde_reproduction_has_independent_author_evidence():
    root = Path(__file__).resolve().parents[2]
    reference = json.loads((root / "tests/references/paper_top82.json").read_text(encoding="utf-8"))
    actual = json.loads((root / "docs/research/evidence/batch2/pde/solver-result.json").read_text(encoding="utf-8"))
    assert reference["source_sha256"] == "3e2fc7e86e21087dc8c84b616feb3a35a7eb7379ae58beff3a216d51556201da"
    assert compare(actual, reference)["native_code_match"]
    assert actual["iterations"] == 461


def test_ordered_simp_original_formula_is_not_misreported_as_a_match(tmp_path):
    report = run_case("ordered_simp", tmp_path)
    errors = report["checks"]["original_2017_formula_max_errors"]
    assert errors[0] < 1e-8
    assert errors[1] > .07 and errors[2] > .09
    assert report["checks"]["original_2017_reproduction_to_fix"]


def test_volume_preserving_companion_is_registered_once_its_binary_limit_is_settled(tmp_path):
    assert metadata("heaviside_volume")[0] in problem_names()
    assert "QUARANTINED" not in description("heaviside_volume").setup
    probe = run_case("heaviside_volume", tmp_path)["checks"]["saturation_probe"]
    assert probe["all_solid_adjoint_finite"] and probe["mixed_binary_refused"]
    assert probe["all_solid_identity_fd_error"] < 1e-4


def test_volume_preserving_projection_refuses_binary_updaters_only_as_first_filter():
    from toporia.framework import Solver
    from toporia.plugins.filters.heaviside import HeavisideFilter
    projection = HeavisideFilter(eta_mode="volume_preserving")
    first = Solver(method="q4+tobs", filter_specs=[{"type": "heaviside", "eta_mode": "volume_preserving"}])
    with pytest.raises(ValueError, match="first filter"):
        projection.setup(None, first)
    behind = Solver(method="q4+tobs", filter_specs=[{"type": "density"},
                                                    {"type": "heaviside", "eta_mode": "volume_preserving"}])
    projection.setup(None, behind)


def test_original_capture_refuses_changed_source_before_matlab(tmp_path):
    from experiments.research_capture import capture
    (tmp_path / "top82.m").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="MATLAB was not started"):
        capture(tmp_path, "must-not-run", tmp_path / "capture")


def test_recipes_do_not_share_mutable_parameters():
    _, first = recipe("sinh")
    first.interpolation["penal"] = 99.
    _, second = recipe("sinh")
    assert second.interpolation["penal"] == 3.1
    _, scheduled = recipe("schedule_geometric")
    scheduled.schedules[0]["end"] = 4.
    assert recipe("schedule_geometric")[1].schedules[0]["end"] == 128.
