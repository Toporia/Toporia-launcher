"""Independent ray fixtures, PDE limits and complete manufacturing adjoints."""

from types import SimpleNamespace

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.framework.problem.scenario import EnforcedArea
from toporia.plugins.filters.machining import MachiningFilter
from toporia.plugins.problems import get_run


def make_filter(shape=(7, 11), spacing=None, solid=None, **settings):
    spacing = spacing or (1.0,) * len(shape)
    problem = SimpleNamespace(shape=shape, dx=spacing[-1], dy=spacing[-2],
                              dz=spacing[0], passive_elements=False if solid is None else solid)
    if "tool_sides" in settings:
        sides = settings.pop("tool_sides").split(",")
        settings.update({f"from_{word}_{axis}": sign + axis in sides
                         for axis in "xyz" for word, sign in (("pos", "+"), ("neg", "-"))})
    filt = MachiningFilter(**settings)
    filt.setup(problem, None)
    return filt


def ray_shadow(x, side):
    """Independent binary visibility from a box face: any preceding solid blocks a tool."""
    axis = x.ndim - 1 - "xyz".index(side[1])
    ray = np.moveaxis(x, axis, 0)
    if side[0] == "+":
        ray = ray[::-1]
    out = np.maximum.accumulate(ray, axis=0)
    if side[0] == "+":
        out = out[::-1]
    return np.moveaxis(out, 0, axis)


def test_registered_conformance():
    conformance(MachiningFilter).assert_ok()


@pytest.mark.parametrize("shape", [(7, 11), (5, 7, 9)])
def test_binary_result_matches_independent_tool_rays_in_the_low_diffusion_limit(shape):
    x = np.random.default_rng(31).integers(0, 2, shape).astype(float)
    sides = ["+x", "-x", "+y", "-y"] + (["+z", "-z"] if len(shape) == 3 else [])
    for side in sides:
        output = make_filter(shape, tool_sides=side, peclet=1e8).forward(x)
        np.testing.assert_array_equal(output > 0.5, ray_shadow(x, side) > 0)
    output = make_filter(shape, tool_sides=",".join(sides), peclet=1e8).forward(x)
    expected = np.minimum.reduce([ray_shadow(x, side) for side in sides])
    np.testing.assert_array_equal(output > 0.5, expected > 0)


def test_an_enclosed_cavity_is_filled_but_an_accessible_channel_remains_open():
    ring = np.zeros((11, 15))
    ring[2:9, 3:12] = 1
    ring[4:7, 5:10] = 0
    filt = make_filter(ring.shape, tool_sides="+x,-x,+y,-y", peclet=1e8)
    assert np.min(filt.forward(ring)[4:7, 5:10]) > 0.99
    ring[4:7, 10:] = 0
    assert np.max(filt.forward(ring)[4:7, 5:10]) < 0.01


def test_transport_converges_to_a_cumulative_source_for_a_cartesian_ray():
    x = np.zeros((1, 15))
    x[0, 3:8] = 0.12
    errors = []
    expected = np.cumsum(x.ravel())
    for pe in (1e5, 1e6, 1e7):
        filt = make_filter(x.shape, tool_sides="-x", peclet=pe)
        lu, rhs = filt._systems[0]
        shadow = lu.solve(filt._source * x.ravel() + rhs)
        errors.append(np.max(np.abs(shadow - expected)))
    assert errors[1] < errors[0] / 9
    assert errors[2] < errors[1] / 9
    assert errors[-1] < 1e-4


@pytest.mark.parametrize("shape,spacing,sides", [
    ((5, 8), (0.7, 1.2), "+x,-y"),
    ((3, 4, 5), (1.1, 0.7, 1.2), "+x,-y,+z"),
])
@pytest.mark.parametrize("with_solid", [False, True])
def test_exact_full_adjoint_including_robin_passive_boundaries_mean_and_projection(
        shape, spacing, sides, with_solid):
    rng = np.random.default_rng(19)
    solid = np.zeros(shape, dtype=bool)
    if with_solid:
        solid[(0,) * len(shape)] = True
    filt = make_filter(shape, spacing, solid, tool_sides=sides)
    x = rng.uniform(0.02, 0.16, shape)
    seed = rng.normal(size=shape)
    gradient = filt.backward(x, seed)
    numerical = np.zeros(shape)
    for index in np.ndindex(shape):
        plus, minus = x.copy(), x.copy()
        plus[index] += 1e-6
        minus[index] -= 1e-6
        numerical[index] = np.sum(seed * (filt.forward(plus) - filt.forward(minus))) / 2e-6
    np.testing.assert_allclose(gradient, numerical, atol=2e-8, rtol=2e-6)
    assert np.all(gradient[solid] == 0)


def test_passive_material_casts_a_shadow_even_when_the_incoming_design_is_void():
    solid = np.zeros((7, 11), dtype=bool)
    solid[3, 6] = True
    filt = make_filter(solid.shape, solid=solid, tool_sides="+x", peclet=1e8)
    output = filt.forward(np.zeros(solid.shape))
    assert output[3, 6] == 1
    assert np.min(output[3, :6]) > 0.99
    assert np.max(output[3, 7:]) < 0.01


def test_zero_and_full_fields_are_bounded_and_length_units_do_not_change_the_map():
    shape = (5, 7, 9)
    filt = make_filter(shape, tool_sides="+x,-y,+z")
    scaled = make_filter(shape, (1000,) * 3, tool_sides="+x,-y,+z")
    for x in (np.zeros(shape), np.ones(shape), np.random.default_rng(2).uniform(0, 0.2, shape)):
        out = filt.forward(x)
        assert np.min(out) >= 0 and np.max(out) <= 1
        np.testing.assert_allclose(out, scaled.forward(x), atol=2e-14)


@pytest.mark.parametrize("settings", [{"from_pos_y": False},
                                      {"peclet": np.inf}, {"peclet": 0},
                                      {"beta": 1}, {"eta": 0}, {"power": 0}])
def test_invalid_settings_fail_with_an_explanation(settings):
    with pytest.raises(ValueError, match="Tool sides|Machining needs"):
        MachiningFilter(**settings)


def test_unsupported_geometry_is_refused_before_optimisation():
    with pytest.raises(ValueError, match="3-D"):
        make_filter(tool_sides="+z")
    with pytest.raises(ValueError, match="forced-void"):
        MachiningFilter().setup(SimpleNamespace(shape=(5, 7), void_elements=True), None)


@pytest.mark.parametrize("overrides,message", [
    ({"representation": {"type": "bspline"}}, "element densities"),
    ({"filter_specs": [{"type": "machining"}, {"type": "density"}]}, "last filter"),
    ({"volfrac": 0.3, "enforced_areas": [EnforcedArea(
        [(0, 17), (60, 17), (60, 20), (0, 20)], "full")]}, "shadows.*volume budget"),
])
def test_invalid_pipeline_or_infeasible_passive_shadow_is_refused(overrides, message):
    run = get_run("Cantilever 3D").updated(method="h8+mma", filter_specs=[{"type": "machining"}])
    with pytest.raises(ValueError, match=message):
        initialized_method(run.updated(**overrides))


@pytest.mark.parametrize("preset", ["MBB Beam", "Cantilever 3D"])
def test_default_start_avoids_saturation_and_a_short_run_changes_the_design(preset):
    run = get_run(preset).updated(save_every=0, max_iter=8, tol=0.0,
                                 filter_specs=[{"type": "density"}, {"type": "machining"}])
    if preset == "MBB Beam":
        run = run.updated(method="q4+mma", m=0.4, method_params={"move": 0.01, "asyinit": 0.03,
                          "asyincr": 1.05, "asydecr": 0.65})
    else:
        run = run.updated(method="h8+mma", method_params={"move": 0.01, "asyinit": 0.03,
                          "asyincr": 1.05, "asydecr": 0.65})
    method = initialized_method(run)
    model = method._model
    start = model.initial_design()
    density = model.physical(start)
    assert density.sum() == pytest.approx(model.volume_limit, rel=1e-9)
    before = model.evaluate(start).objective
    for i in range(1, 9):
        previous_x, previous_density = method.x.copy(), method.get_density().copy()
        method.step(i)
        expected = max(np.max(np.abs(method.x - previous_x)),
                       np.max(np.abs(method.get_density() - previous_density)))
        assert method.get_change() == pytest.approx(expected)
    after = model.evaluate(method.x).objective
    assert np.all(np.isfinite(method.get_density()))
    assert np.max(np.abs(method.x - start)) > 1e-4
    assert after < before
    assert model.physical(method.x).sum() <= model.volume_limit * 1.01


@pytest.mark.parametrize("preset", ["MBB Beam", "Cantilever 3D"])
def test_compliance_and_physical_volume_gradients_through_the_whole_model(preset):
    run = get_run(preset).updated(filter_specs=[{"type": "density"}, {"type": "machining"}],
                                 m=0.4)
    method = initialized_method(run)
    model, x = method._model, method.x.copy()
    rng = np.random.default_rng(5)
    direction = rng.normal(size=x.shape)
    direction /= np.linalg.norm(direction)
    result = model.evaluate(x)
    # The thin H8 start is ill conditioned; a larger directional step avoids
    # cancellation of the state solver's roundoff in the compliance difference.
    step = 1e-4
    plus = model.evaluate(x + step * direction)
    minus = model.evaluate(x - step * direction)
    assert np.sum(result.objective_gradient * direction) == pytest.approx(
        (plus.objective - minus.objective) / (2 * step), rel=2e-5, abs=2e-5)
    assert np.sum(result.volume_gradient * direction) == pytest.approx(
        (plus.volume - minus.volume) / (2 * step), rel=2e-6)
