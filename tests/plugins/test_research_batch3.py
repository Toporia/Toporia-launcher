"""Research evidence must retain physical fields, genuine checks and limitations."""

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.research_batch3 import cap_probe, representation_probe, run_case, update_probe
from experiments.research_pto_attempt import SOURCE_HASH, capture
from experiments.research_publish3 import publish
from toporia.engine.loop import initialized_method
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.physics.q4_plane_stress import solve_fea
from toporia.plugins.problems import get_run, problem_description, problem_names
from toporia.plugins.problems._research_batch3 import CASES, metadata, recipe

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("case_id", CASES)
def test_real_discovered_recipe_executes_and_closes(case_id):
    name = metadata(case_id)[0]
    assert name in problem_names()
    run = get_run(name)
    text = problem_description(name)
    assert text.functions == (CASES[case_id]["function"],)
    assert text.equations and text.symbols and text.limitations
    method = initialized_method(run)
    try:
        method.step(1)
        assert np.isfinite(method.get_responses()["objective"])
        assert np.isfinite(method.get_density()).all()
    finally:
        method.close()


@pytest.mark.parametrize("case_id", [k for k, v in CASES.items() if v["function"].startswith("representation:")])
def test_representation_jacobian_in_five_independent_directions(case_id, tmp_path):
    report = representation_probe(case_id, tmp_path)
    assert report["checks_passed"], report


@pytest.mark.parametrize("case_id", ["adam", "simpl"])
def test_equation_checks_do_not_claim_paper_figure_matching(case_id, tmp_path):
    report = update_probe(case_id, tmp_path)
    assert report["checks_passed"]
    assert "scope" in report


def test_local_cap_fractions_against_independent_cross_section_integrals(tmp_path):
    assert cap_probe(tmp_path)["cap_quadrature_pass"]


@pytest.mark.parametrize("case_id", CASES)
def test_recorded_density_reproduces_fresh_compliance_and_honest_status(case_id):
    folder = ROOT / "docs/research/evidence/batch3" / case_id
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    density = np.loadtxt(folder / "final-density.csv", delimiter=",")
    scenario, solver = recipe(case_id)
    problem = make_problem(scenario, solver.m)
    assert density.shape == problem.shape
    # Re-evaluate the actual physical field, with no extra representation/filter.
    penal = 1. if CASES[case_id]["function"].startswith("method:") else 3.
    compliance = float(solve_fea(problem, density, penal=penal)[2])
    assert compliance == pytest.approx(report["fresh_final_compliance"], rel=1e-9)
    assert density.mean() == pytest.approx(report["physical_volume_fraction"], abs=1e-14)
    assert report["feasible_volume_1e_4"] == (density.mean() <= scenario.volfrac+1e-4)
    assert report["functions"] == [CASES[case_id]["function"]]
    assert report["paper_status"] == "paper_reproduction_to_fix"
    assert report["checks"]["checks_passed"]
    assert report["iteration_override"] is None
    assert report["scenario"]["volfrac"] == scenario.volfrac
    assert report["resolved_method_params"]
    assert (folder / "figure.png").is_file()
    assert (ROOT / "docs/research/to-fix" / ("batch3-" + case_id) / "README.md").is_file()


def test_fresh_driver_retains_the_post_update_field_and_iteration_override(tmp_path):
    report = run_case("mma", tmp_path, max_iter=2)
    assert report["iterations"] == 2
    assert report["iteration_override"] == 2
    assert report["final_check_extra_model_evaluations"] == 1
    assert report["fresh_final_compliance"] != report["last_recorded_objective"]
    assert (tmp_path / "mma" / "final-variables.csv").is_file()


def test_publisher_rejects_shortened_capture_and_uncertified_match(tmp_path):
    source = tmp_path / "source"
    first = next(iter(CASES))
    folder = source / first
    folder.mkdir(parents=True)
    record = dict(checks=dict(checks_passed=True), iteration_override=2)
    (folder / "report.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="iteration override"):
        publish(source, tmp_path / "target")
    record.update(iteration_override=None, paper_status="native_code_match")
    (folder / "report.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="cannot certify"):
        publish(source, tmp_path / "target")


def test_recipes_do_not_share_mutable_parameters():
    for case_id in CASES:
        _, first = recipe(case_id)
        _, second = recipe(case_id)
        first.method_params["not_a_real_setting"] = 1
        first.filter_specs.append(dict(type="not_a_real_filter"))
        first.representation["not_a_real_setting"] = 1
        assert "not_a_real_setting" not in second.method_params
        assert "not_a_real_setting" not in second.representation
        assert all(s["type"] != "not_a_real_filter" for s in second.filter_specs)


def test_native_ptoc_capture_checks_source_before_launching_matlab(tmp_path):
    (tmp_path / "PTOc_mbb.m").write_text("changed author code")
    with pytest.raises(ValueError, match="hash differs"):
        capture(tmp_path, "not-a-matlab-executable")


def test_ptoc_attempt_retains_the_algorithm_mismatch_and_checks_common_physics():
    reference = json.loads((ROOT / "tests/references/paper_ptoc.json").read_text(encoding="utf-8"))
    report = json.loads((ROOT / "docs/research/evidence/batch3/pto/paper-attempt/report.json").read_text(encoding="utf-8"))
    assert reference["source_sha256"] == SOURCE_HASH
    assert report["source_sha256"] == SOURCE_HASH
    assert report["author_field_physics_match"]
    assert not report["native_code_match"]
    assert report["paper_status"] == "paper_reproduction_to_fix"
    assert report["density_max_error"] > report["tolerances"]["density_max_abs"]
