"""test_problem_roles.py — springs, output ports and heat loss on the Problem page (To do item 16).

A copied compliant mechanism keeps its springs and port as editable objects and solves
the same problem; a heat-loss boundary lets heat leave without a sink; springs are refused
by a model that cannot hold them; and bad objects are refused before the run.
"""

from dataclasses import replace

import pytest

from toporia_core.engine.loop import initialized_method
from toporia_core.framework import LoadCase, Scenario
from toporia_core.framework.problem.regions import validate_object
from toporia_gui.geometry import make_object, objects_from_scenario
from toporia_library.problems import get_run


def _evaluate(run):
    method = initialized_method(run)
    model = method._model
    return model, model.evaluate(method.x, gradients=False)


def test_a_copied_mechanism_keeps_its_springs_and_port_as_objects():
    run = get_run("Force Inverter")
    objects = objects_from_scenario(run.scenario)
    roles = [obj["role"] for obj in objects]
    assert roles.count("spring") == len([s for s in run.scenario.point_springs if s.stiffness > 0])
    assert roles.count("port") == 1
    custom = replace(run, scenario=replace(run.scenario, regions=objects, point_springs=[]))
    _, legacy = _evaluate(run)
    _, copied = _evaluate(custom)
    assert copied.objective == pytest.approx(legacy.objective, rel=1e-9)


def test_a_port_object_decides_where_the_output_is_measured():
    run = get_run("Force Inverter")
    objects = objects_from_scenario(run.scenario)
    port = next(obj for obj in objects if obj["role"] == "port")
    port["direction"] = port.get("direction", 180.0) + 180.0          # the opposite way
    custom = replace(run, scenario=replace(run.scenario, regions=objects, point_springs=[]))
    _, legacy = _evaluate(run)
    _, flipped = _evaluate(custom)
    assert flipped.objective == pytest.approx(-legacy.objective, rel=1e-9)


def _plate(objects, **changes):
    scenario = Scenario(Lx=20.0, Ly=10.0, regions=objects, load_cases=[LoadCase(Fmag=0.0, Fa=0.0, weight=1.0)],
                        E0=1.0, Emin=1e-3, volfrac=0.5, objective={"type": "thermal_compliance"}, **changes)
    run = get_run("Heat Sink").updated(method="q4_heat+mma", max_iter=2)
    return replace(run, scenario=scenario, solver=replace(run.solver, m=1.0, filter_specs=[{"type": "density"}]))


def test_heat_leaves_through_a_heat_loss_boundary_without_a_sink():
    def edge(coefficient):
        return make_object("line", (20.0, 0.0, 0.0), (0.0, 10.0, 0.0), "heat_loss", coefficient=coefficient)
    warm = _evaluate(_plate([edge(1.0)]))[1].objective
    cool = _evaluate(_plate([edge(10.0)]))[1].objective
    assert 0 < cool < warm
    with pytest.raises(ValueError, match="support or a heat loss"):
        initialized_method(_plate([]))


def test_springs_need_a_model_that_holds_them():
    run = get_run("MBB Beam").updated(method="q4+oc")
    objects = objects_from_scenario(run.scenario)
    objects.append(make_object(position=(30.0, 0.0, 0.0), role="spring", axes=["y"], stiffness=0.1))
    with pytest.raises(ValueError, match="spring"):
        initialized_method(replace(run, scenario=replace(run.scenario, regions=objects)))


@pytest.mark.parametrize("obj, message", [
    (make_object(role="spring", axes=[], stiffness=1.0), "axis"),
    (make_object(role="spring", stiffness=0.0), "stiffness"),
    (make_object("line", role="port"), "a point"),
    (make_object("line", role="heat_loss", coefficient=-1.0), "coefficient"),
    (make_object(role="magnet"), "Region role must be one of"),
])
def test_bad_objects_are_refused(obj, message):
    with pytest.raises(ValueError, match=message):
        validate_object(obj, 2)
