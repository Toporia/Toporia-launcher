"""Physical editor integration: IDs, selection, transforms, undo and project persistence."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from toporia.apps.gui.editor import ProblemEditor
from toporia.apps.gui.geometry import make_object, objects_from_scenario
from toporia.framework.problem.scenario import Scenario
from toporia.plugins.problems import get_run, problem_names


@pytest.fixture(scope="module")
def editor():
    app = QApplication.instance() or QApplication([])
    editor = ProblemEditor()
    yield editor
    editor.deleteLater()
    app.processEvents()


def test_scene_selection_numeric_edits_and_undo_share_one_definition(editor):
    editor.load(Scenario(), [], False)
    obj = make_object("rectangle", (10, 5, 0), (20, 10, 1), "void")
    editor.add_object(obj)
    assert editor.selected_id() == obj["id"]
    editor.fields["x"].setValue(15)
    editor.fields["angle"].setValue(30)
    editor.fields["scale"].setValue(2)
    editor.role.setCurrentIndex(editor.role.findData("load"))
    editor.fields["fx"].setValue(8)
    editor.apply_inspector()
    assert editor.objects[0]["position"] == [15, 5, 0]
    assert editor.objects[0]["size"] == [40, 20, 1]
    assert editor.objects[0]["rotation"][2] == 30
    assert editor.objects[0]["force"][0] == 8
    editor.undo()
    assert editor.objects == [obj]
    editor.redo()
    assert editor.objects[0]["role"] == "load"
    editor.select(obj["id"])
    editor.delete_selected()
    assert editor.objects == []
    editor.undo()
    assert editor.objects[0]["id"] == obj["id"]


def test_graphical_tools_create_in_physical_coordinates(editor):
    editor.load(Scenario(), [], False)
    editor.set_tool("line")
    editor._place(0, 0)
    editor._place(0, 50)
    assert editor.objects[0]["size"] == [0, 50, 0]
    editor.set_tool("rectangle")
    editor._place(40, 20)
    editor._place(20, 10)
    assert editor.objects[1]["position"] == [20, 10, 0]
    assert editor.objects[1]["size"] == [20, 10, 1]
    editor.move_object(editor.objects[1]["id"], 12, 13)
    assert editor.objects[1]["position"] == [12, 13, 0]
    editor.undo()
    assert editor.objects[1]["position"] == [20, 10, 0]


@pytest.mark.parametrize("name", problem_names())
def test_reference_geometry_is_visible_but_cannot_be_edited(editor, name):
    scenario = get_run(name).scenario
    editor.load(scenario, None, True)
    before = editor._snapshot()
    assert editor.object_list.count() == len(editor.objects)
    editor.add_object(make_object())
    editor.apply_domain()
    editor.undo()
    assert editor._snapshot() == before
    assert len(objects_from_scenario(scenario)) > 0


def test_empty_custom_problem_stays_empty_and_domain_edits_do_not_move_objects(editor):
    editor.load(Scenario(), [], False)
    assert editor.objects == []
    obj = make_object(position=(10, 5, 0))
    editor.add_object(obj)
    editor.domain_fields["Lx"].setValue(200)
    editor.apply_domain()
    assert editor.scenario.Lx == 200
    assert editor.objects == [obj]
