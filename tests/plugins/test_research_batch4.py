"""Research recipes must retain reproducible fields and honest comparison scopes."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.research_batch4 import science_case
from experiments.research_gradients import at_schedule_end
from experiments.research_inventory import inventory
from experiments.research_publish4 import CASE_IDS, publish
from toporia.engine.loop import initialized_method
from toporia.framework.problem.run import Run
from toporia.plugins.problems import get_run, problem_description, problem_names
from toporia.plugins.problems._research_batch4 import CASES, POSTS, metadata, recipe

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", CASES)
def test_registered_companions_execute_without_new_framework_contracts(name):
    label = metadata(name)[0]
    assert label in problem_names()
    assert problem_description(label).functions == CASES[name]["functions"]
    method = initialized_method(get_run(label))
    try:
        method.step(1)
        assert np.isfinite(method.get_responses()["objective"])
        assert np.isfinite(method.get_density()).all()
    finally:
        method.close()


@pytest.mark.parametrize("name", CASE_IDS)
def test_curated_reports_retain_the_actual_final_fields_and_comparison_scope(name):
    folder = ROOT / "docs/research/evidence/batch4" / name
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    assert report["checks"]["checks_passed"]
    assert report["paper_status"] in {"paper_reproduction_to_fix", "not_applicable_engineering_demo"}
    assert report["iteration_override"] is None
    assert (folder / "figure.png").exists()
    assert (folder / "description.html").exists()
    if name in POSTS:
        source = ROOT / report["source_field"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == report["source_field_sha256"]
        for filename in report["files"]:
            assert (folder / "exports" / filename).is_file()
        return
    scenario, solver = recipe(name)
    method = initialized_method(Run(scenario, solver))
    at_schedule_end(method, solver)      # a projection or tolerance continuation ends at its last value
    try:
        model = method._model
        # Set first-design eigenvalue normalization at the same point as capture.
        model.evaluate(model.initial_design(), gradients=False)
        variables = np.load(folder / "final-variables.npy", allow_pickle=False)
        field = np.load(folder / "final-density.npy", allow_pickle=False)
        assert model.physical(variables) == pytest.approx(field, abs=1e-12)
        fresh = model.evaluate(variables, gradients=False)
        assert fresh.objective == pytest.approx(report["fresh_final_objective"], rel=1e-6)
        assert field.mean() == pytest.approx(report["physical_volume_fraction"], abs=1e-14)
        # Captured errors pass a tighter regression bound than the audit gate.
        assert max(report["checks"]["directional_gradient_errors"]) < 1e-4
    finally:
        method.close()


def test_all_new_function_ids_are_real_and_have_explicit_evidence():
    report = inventory()
    functions = {row["id"]: row for row in report["functions"]}
    expected = {identity for case in CASES.values() for identity in case["functions"]}
    assert expected <= functions.keys()
    assert all(functions[key]["status"] != "pending" for key in expected)
    assert all(functions[key]["research_cases"] for key in expected)


def test_independent_probes_remain_separate_from_paper_matching():
    root = ROOT / "docs/research/evidence/batch4"
    for name in ("heat2d", "heat3d", "dynamic", "dynamic_pymoto", "buckling", "nonlinear", "mechanism", "phase_field"):
        report = json.loads((root / name / "report.json").read_text(encoding="utf-8"))
        assert report["checks"]["checks_passed"]
        assert report["paper_status"] == "paper_reproduction_to_fix"
    native = json.loads((root / "solid3d/native-scalar-comparison.json").read_text(encoding="utf-8"))
    assert native["checks"]["native_scalar_pass"]
    assert native["actual"]["iterations"] == 39
    assert native["author_source"]["sha256"]
    fixture = ROOT / "tests/references/matlab.json"
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == native["fixture_sha256"]


def test_short_diagnostic_is_recorded_but_refused_for_publication(tmp_path):
    report = science_case("heat3d", tmp_path, max_iter=2)
    assert report["iteration_override"] == 2
    # Publisher encounters solid3d first: supply a deliberately shortened record.
    (tmp_path / "solid3d").mkdir()
    (tmp_path / "solid3d/report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="failed/shortened"):
        publish(tmp_path, tmp_path / "published")


def test_diagnostic_recipes_do_not_share_mutable_configuration():
    for name in CASES:
        _, a = recipe(name)
        _, b = recipe(name)
        a.method_params["not_a_real_setting"] = 1
        a.filter_specs.append(dict(type="not_a_real_filter"))
        assert "not_a_real_setting" not in b.method_params
        assert all(s["type"] != "not_a_real_filter" for s in b.filter_specs)
