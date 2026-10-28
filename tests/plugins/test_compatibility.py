"""Every part's help says what it works with, and every part has a preset to try it in."""

import pytest

from toporia.plugins.compatibility import demo_presets, function_id, use_when, works_with
from toporia.plugins.filters import FILTERS
from toporia.plugins.interpolations import INTERPOLATIONS
from toporia.plugins.methods import METHODS, method_class
from toporia.plugins.models import MODELS
from toporia.plugins.postprocessors import POSTPROCESSORS
from toporia.plugins.representations import REPRESENTATIONS
from toporia.plugins.responses import RESPONSES
from toporia.plugins.schedules import SCHEDULES
from toporia.plugins.updaters import UPDATERS

PARTS = [cls for registry in (FILTERS, INTERPOLATIONS, REPRESENTATIONS, RESPONSES, SCHEDULES, POSTPROCESSORS,
                              MODELS, UPDATERS, METHODS) for cls in registry.classes()]


@pytest.mark.parametrize("cls", PARTS, ids=function_id)
def test_every_part_states_what_it_works_with(cls):
    lines = works_with(cls)
    assert lines, f"{function_id(cls)} says nothing about compatibility"
    assert not any("could not be worked out" in line for line in lines)


@pytest.mark.parametrize("cls", PARTS, ids=function_id)
def test_every_part_describes_itself(cls):
    # The help's "What it is" is the class docstring; an inherited one describes the base class instead.
    assert cls.__dict__.get("__doc__"), f"{function_id(cls)} has no docstring of its own"


@pytest.mark.parametrize("cls", PARTS, ids=function_id)
def test_every_part_says_when_to_use_it(cls):
    assert cls.__dict__.get("use_when"), f"{function_id(cls)} has no use_when of its own"


def test_a_composed_method_joins_its_parts_advice():
    text = use_when(method_class("q4+mma"))
    assert text.startswith("2-D Q4 plane stress") and "Method of moving asymptotes" in text


@pytest.mark.parametrize("cls", PARTS, ids=function_id)
def test_every_part_has_a_preset_to_try_it_in(cls):
    assert demo_presets(function_id(cls)), f"no preset exercises {function_id(cls)}: add one"


def test_restrictions_are_stated_where_they_apply():
    # Local stress is enforced only by its own augmented-Lagrangian updater.
    stress = " ".join(works_with(RESPONSES.get("local_stress")))
    assert "Updaters that can enforce it: Augmented Lagrangian" in stress
    assert "Optimality criteria" not in stress
    # OC cannot drive a non-element representation, and both sides say so.
    assert any("only the element-density representation" in line for line in works_with(method_class("q4+oc")))
    assert any("Optimality criteria" in line for line in works_with(REPRESENTATIONS.get("mmc")))
    # Dimensions come from the declarations.
    assert works_with(MODELS.get("h8"))[0] == "3-D only."
    assert works_with(MODELS.get("q4"))[0] == "2-D only."


def test_dedicated_presets_come_first():
    presets = demo_presets("filter:heaviside")
    assert presets[0].startswith(("Research:", "Paper:"))
    assert "MBB Beam (Robust)" in presets
