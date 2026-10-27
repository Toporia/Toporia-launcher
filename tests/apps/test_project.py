"""Project persistence: portable inputs, independent results, lossless problem files."""

import json

import pytest

from toporia.apps.gui.project import ProblemDocument, Project
from toporia.framework.problem.files import save
from toporia.plugins.problems import get_run, problem_names


@pytest.mark.parametrize("name", problem_names())
def test_projects_round_trip_every_benchmark_without_output_paths(tmp_path, name):
    project = Project(name, get_run(name), benchmark=name, notes="Research notes: α", study={"mode": "Sweep"})
    path = project.save(tmp_path / "project.top")
    loaded = Project.load(path)
    assert loaded.payload() == project.payload()
    assert loaded.run.scenario == project.run.scenario
    assert loaded.run.solver == project.run.solver
    assert loaded.results_dir == tmp_path / "results"
    assert "dir" not in json.loads(path.read_text(encoding="utf-8"))["output"]
    assert list(tmp_path.iterdir()) == [path]


def test_problem_export_contains_no_solver_or_results(tmp_path):
    original = ProblemDocument(get_run("MBB Beam").scenario, objects=[])
    path = original.save(tmp_path / "beam.pro")
    assert ProblemDocument.load(path) == original
    assert set(json.loads(path.read_text())) == {"kind", "format", "scenario", "objects"}
    legacy = save(original.scenario, tmp_path / "scenario.json")
    assert ProblemDocument.load(legacy).scenario == original.scenario
    from toporia.framework.problem.files import load
    assert load(path, "scenario") == original.scenario


def test_failed_save_keeps_existing_document_and_location(tmp_path, monkeypatch):
    project = Project("Beam", get_run("MBB Beam"))
    path = project.save(tmp_path / "project.top")
    before = path.read_bytes()
    project.view = {"bad": float("nan")}
    with pytest.raises(ValueError):
        project.save()
    assert path.read_bytes() == before
    assert project.path == path
    project.view = {}
    monkeypatch.setattr("toporia.apps.gui.project.os.replace", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        project.save()
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("change", [{"format": 2}, {"format": True}, {"kind": "scenario"},
                                    {"unknown": "do not discard me"}, {"study": []}, {"objects": {}},
                                    {"output": {"dir": "elsewhere"}}])
def test_project_loader_rejects_incompatible_documents(tmp_path, change):
    data = Project("Beam", get_run("MBB Beam")).payload() | change
    path = tmp_path / "bad.top"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        Project.load(path)


def test_editor_objects_are_the_saved_headless_definition_and_are_not_duplicated(tmp_path):
    from toporia.apps.gui.geometry import make_object
    objects = [make_object(position=(3, 4, 0))]
    project = Project("Explicit", get_run("MBB Beam"), objects=objects)
    path = project.save(tmp_path / "project.top")
    data = json.loads(path.read_text())
    assert "regions" not in data["scenario"]
    assert Project.load(path).run.scenario.regions == objects


@pytest.mark.parametrize("view", [{"method_positions": []}, {"method_positions": {"block": [1]}},
                                  {"camera3d": [[1, 2], [0, 0, 0], [0, 0, 1]]}])
def test_invalid_view_state_is_rejected_before_graphics_widgets(tmp_path, view):
    data = Project("Beam", get_run("MBB Beam"), view=view).payload()
    path = tmp_path / "bad.top"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        Project.load(path)
