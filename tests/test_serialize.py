"""test_serialize.py — scenario and solver files, fingerprints and run provenance."""

import json
from dataclasses import replace

import pytest

from toporia.engine.loop import run_single
from toporia.framework import Scenario, Solver
from toporia.framework.parts.method import OBJECTIVE
from toporia.framework.problem.files import fingerprint, from_dict, load, save
from toporia.plugins.problems import get_run, problem_names


@pytest.mark.parametrize("name", problem_names())
def test_every_preset_round_trips_through_json(tmp_path, name):
    run = get_run(name)
    for obj, kind in ((run.scenario, "scenario"), (run.solver, "solver")):
        path = save(obj, tmp_path / f"preset.{kind}.json")
        assert load(path) == obj
        assert load(path, kind) == obj
        assert fingerprint(load(path)) == fingerprint(obj)


def test_a_file_only_needs_what_differs_from_the_defaults(tmp_path):
    path = tmp_path / "tiny.scenario.json"
    path.write_text(json.dumps({"kind": "scenario", "format": 1, "volfrac": 0.3}))
    assert load(path) == Scenario(volfrac=0.3)


def test_the_fingerprint_is_stable_and_sensitive():
    scenario = get_run("MBB Beam").scenario
    assert fingerprint(scenario) == fingerprint(replace(scenario))
    assert fingerprint(replace(scenario, volfrac=0.4)) != fingerprint(scenario)
    assert len(fingerprint(scenario)) == 12


def test_unknown_fields_are_rejected(tmp_path):
    path = tmp_path / "bad.scenario.json"
    path.write_text(json.dumps({"kind": "scenario", "format": 1, "colour": "red"}))
    with pytest.raises(ValueError, match="colour"):
        load(path)


def test_unknown_nested_fields_are_rejected(tmp_path):
    path = tmp_path / "bad.scenario.json"
    path.write_text(json.dumps({"kind": "scenario", "format": 1, "load_cases": [{"Fmag": 1, "Fangle": 0}]}))
    with pytest.raises(ValueError, match="Fangle"):
        load(path)


def test_the_wrong_kind_is_rejected(tmp_path):
    path = save(Solver(), tmp_path / "x.solver.json")
    with pytest.raises(ValueError, match="solver file"):
        load(path, "scenario")


def test_a_newer_format_is_rejected(tmp_path):
    path = tmp_path / "future.solver.json"
    path.write_text(json.dumps({"kind": "solver", "format": 99}))
    with pytest.raises(ValueError, match="format"):
        load(path)


def test_every_run_records_its_provenance(tmp_path):
    run = get_run("MBB Beam").updated(m=0.25, max_iter=3, tol=0.0, save_every=0).with_output_dir(tmp_path)
    run_single(run)
    record = json.loads((tmp_path / "run.json").read_text())

    assert record["scenario"]["fingerprint"] == fingerprint(run.scenario)
    assert record["solver"]["fingerprint"] == fingerprint(run.solver)
    # The record holds the full definitions, so a result can be re-run from it alone.
    assert from_dict(Scenario, record["scenario"]["definition"]) == run.scenario
    assert from_dict(Solver, record["solver"]["definition"]) == run.solver
    assert record["result"]["iterations"] == 3
    assert "iteration limit" in record["result"]["stop_reason"]
    assert OBJECTIVE in record["result"]["final"]
    assert record["software"]["numpy"]
