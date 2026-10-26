"""Explicit region physics: no fallback, independent forces and resolution invariance."""

from dataclasses import replace

import numpy as np
import pytest

from toporia.apps.gui.geometry import make_object, objects_from_scenario
from toporia.framework.problem.files import from_dict, to_dict
from toporia.framework.problem.mesh import make_problem
from toporia.framework.problem.scenario import LoadCase, Scenario
from toporia.plugins.physics.q4_plane_stress import Q4DofLayout
from toporia.plugins.problems import get_run


def beam_objects():
    return [make_object("line", (0, 0, 0), (0, 10, 0), "support"),
            make_object("point", (20, 5, 0), role="load", force=[0, -10, 0])]


def beam(**kwargs):
    return Scenario(Lx=20, Ly=10, regions=beam_objects(), **kwargs)


@pytest.mark.parametrize("resolution", [0.5, 1.0, 2.0])
def test_total_regional_forces_do_not_scale_with_mesh_and_objects_keep_coordinates(resolution):
    scenario = beam()
    objects = scenario.regions.copy()
    problem = make_problem(scenario, resolution)
    layout = Q4DofLayout(problem)
    force = layout.forces[0][1].reshape(-1, 2)
    np.testing.assert_allclose(force.sum(axis=0), [0, -10])
    assert np.count_nonzero(problem.fixed_x_nodes) == problem.nely + 1
    assert scenario.regions == objects


def test_separate_load_objects_keep_their_own_vector_and_case():
    objects = beam_objects() + [make_object("rectangle", (19, 8, 0), (1, 2, 1), "load", force=[7, 0, 0], case=1)]
    scenario = replace(beam(load_cases=[LoadCase(weight=.5), LoadCase(weight=.5)]), regions=objects)
    layout = Q4DofLayout(make_problem(scenario))
    np.testing.assert_allclose(layout.forces[0][1].reshape(-1, 2).sum(axis=0), [0, -10])
    np.testing.assert_allclose(layout.forces[1][1].reshape(-1, 2).sum(axis=0), [7, 0])


@pytest.mark.parametrize("objects,message", [([], "supports"),
    ([beam_objects()[0]], "load object"),
    ([beam_objects()[1]], "supports"),
    ([make_object(position=(0, 0, 0)), beam_objects()[1]], "rigid-body"),
    ([*beam_objects(), make_object("circle", (100, 100, 0), (1, 1, 1), "void")], "no elements"),
    ([*beam_objects(), make_object("rectangle", (1, 1, 0), (4, 4, 1), "solid"),
      make_object("rectangle", (1, 1, 0), (4, 4, 1), "void")], "conflict")])
def test_incomplete_or_ambiguous_regions_are_rejected_without_defaults(objects, message):
    with pytest.raises(ValueError, match=message):
        make_problem(replace(beam(), regions=objects))


def test_custom_scenario_round_trip_and_legacy_serialization_remain_distinct():
    assert "regions" not in to_dict(Scenario())
    scenario = beam()
    assert from_dict(Scenario, to_dict(scenario)) == scenario


def test_copying_mbb_to_explicit_regions_preserves_boundary_conditions_and_forces():
    scenario = get_run("MBB Beam").scenario
    legacy = Q4DofLayout(make_problem(scenario))
    explicit = Q4DofLayout(make_problem(replace(scenario, regions=objects_from_scenario(scenario))))
    np.testing.assert_array_equal(explicit.fixed_dofs, legacy.fixed_dofs)
    np.testing.assert_allclose(explicit.forces[0][1], legacy.forces[0][1], atol=1e-14)


def test_custom_problem_reaches_the_actual_optimizer(tmp_path):
    from toporia.engine.loop import run_single
    from toporia.framework.problem.run import Run
    from toporia.framework.problem.solver import Solver
    cfg = Run(scenario=beam(), solver=Solver(method="q4+oc", m=.5, max_iter=3, filter_specs=[{"type": "density"}]))
    density = run_single(cfg.with_output_dir(tmp_path))
    assert density.shape == (5, 10)
    assert np.isfinite(density).all()
    assert (tmp_path / "run.json").exists()
