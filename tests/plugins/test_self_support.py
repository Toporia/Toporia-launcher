"""Support projection: geometric fixtures and complete layer/physics adjoints."""

from types import SimpleNamespace

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.plugins.filters.self_support import SelfSupportProjection
from toporia.plugins.problems import get_run


def make_filter(shape=(9, 13), spacing=(1.0, 1.0), **settings):
    part = SelfSupportProjection(**settings)
    part.setup(SimpleNamespace(shape=shape, dy=spacing[0], dx=spacing[1]), None)
    return part


def test_conformance():
    conformance(SelfSupportProjection).assert_ok()


@pytest.mark.parametrize("direction", ["+y", "-y", "+x", "-x"])
def test_islands_without_a_build_plate_connection_disappear(direction):
    part = make_filter(direction=direction)
    field = np.zeros((9, 13))
    field[3:6, 5:8] = 1
    assert np.max(part.forward(field)) == 0
    np.testing.assert_allclose(part.forward(np.ones(field.shape)), 1, atol=1e-14)
    np.testing.assert_allclose(part.forward(np.zeros(field.shape)), 0, atol=1e-14)


def test_a_vertical_pillar_is_supported_but_a_long_horizontal_overhang_is_removed():
    field = np.zeros((17, 25))
    field[:13, 4:7] = 1
    field[12, 7:23] = 1
    part = make_filter(field.shape)
    out = part.forward(field)
    assert out[7, 5] > 0.99
    assert np.max(out[12, 15:]) == 0


def test_vertical_only_support_does_not_admit_lateral_source_points():
    field = np.zeros((12, 17))
    field[:8, 8] = 1
    field[8, :] = 1
    part = make_filter(field.shape, angle=90)
    phi = part._supported(field)[0]
    assert phi[8, 8] > 0.9
    assert np.count_nonzero(phi[8]) == 1
    # At 45 degrees, nearby lateral sources can use the resolved support wedge.
    wider = make_filter(field.shape, angle=45)._supported(field)[0]
    assert np.count_nonzero(wider[8]) > 1
    assert wider[8, 0] == 0


def test_a_resolved_45_degree_support_slope_survives_projection():
    y, x = np.indices((22, 35))
    field = ((x >= y) & (x <= y + 4)).astype(float)
    out = make_filter(field.shape).forward(field)
    assert np.min(out[np.arange(3, 18), np.arange(3, 18) + 2]) > 0.95


@pytest.mark.parametrize("direction,spacing", [
    ("+y", (1.0, 1.0)), ("-y", (1.0, 1.0)),
    ("+x", (0.7, 1.1)), ("-x", (0.7, 1.1)),
])
def test_complete_adjoint_includes_all_lower_layers_and_the_local_projection(direction, spacing):
    part = make_filter((6, 9), spacing, direction=direction, beta_local=5, beta_support=7)
    rng = np.random.default_rng(23)
    x, seed = rng.uniform(0.12, 0.7, (6, 9)), rng.normal(size=(6, 9))
    numerical = np.zeros(x.shape)
    for index in np.ndindex(x.shape):
        plus, minus = x.copy(), x.copy()
        plus[index] += 1e-6
        minus[index] -= 1e-6
        numerical[index] = np.sum(seed * (part.forward(plus) - part.forward(minus))) / 2e-6
    np.testing.assert_allclose(part.backward(x, seed), numerical, rtol=2e-6, atol=2e-8)


def test_the_last_layer_transmits_sensitivity_all_the_way_to_the_base():
    part = make_filter((8, 5), angle=90, beta_support=5, beta_local=2)
    x = np.full((8, 5), 0.25)
    seed = np.zeros_like(x)
    seed[-1, 2] = 1
    gradient = part.backward(x, seed)
    assert np.all(gradient[:, 2] > 0)


def test_reflections_rotations_and_a_change_of_length_units_preserve_the_map():
    x = np.random.default_rng(4).uniform(0, 1, (7, 11))
    original = make_filter(x.shape, (0.8, 1.1)).forward(x)
    np.testing.assert_allclose(make_filter(x.shape, (8, 11)).forward(x), original, atol=1e-14)
    flipped = make_filter(x.shape, (0.8, 1.1), direction="-y").forward(x[::-1])
    np.testing.assert_allclose(flipped[::-1], original, atol=1e-14)
    rotated = make_filter(x.T.shape, (1.1, 0.8), direction="+x").forward(x.T)
    np.testing.assert_allclose(rotated.T, original, atol=1e-14)


@pytest.mark.parametrize("settings", [{"direction": "+z"}, {"rmin": np.nan},
                                      {"angle": 0}, {"threshold": 0}, {"beta_support": np.inf}])
def test_invalid_settings_are_refused(settings):
    with pytest.raises(ValueError, match="Self-support"):
        SelfSupportProjection(**settings)


def test_unsupported_geometry_and_unresolved_wedges_are_refused():
    for problem in (SimpleNamespace(shape=(2, 3, 4)),
                    SimpleNamespace(shape=(5, 7), passive_elements=True),
                    SimpleNamespace(shape=(5, 7), void_elements=True),
                    SimpleNamespace(shape=(5, 7), dy=10, dx=1)):
        with pytest.raises(ValueError, match="2-D|forced solid/void|no previous layer"):
            SelfSupportProjection().setup(problem, None)


def test_a_physical_volume_start_and_small_mma_steps_improve_a_cantilever():
    run = get_run("Cantilever").updated(
        method="q4+mma", m=0.4, save_every=0, tol=0,
        interpolation={"type": "ramp", "q": 8}, filter_specs=[{"type": "self_support"}],
        method_params={"move": 0.01, "asyinit": 0.02, "asyincr": 1.05, "asydecr": 0.65})
    method = initialized_method(run)
    model = method._model
    initial = model.evaluate(method.x)
    assert initial.volume == pytest.approx(model.volume_limit, rel=1e-10)
    rng = np.random.default_rng(8)
    direction = rng.normal(size=method.x.shape)
    direction /= np.linalg.norm(direction)
    step = 1e-5
    plus = model.evaluate(method.x + step * direction)
    minus = model.evaluate(method.x - step * direction)
    assert np.sum(initial.objective_gradient * direction) == pytest.approx(
        (plus.objective - minus.objective) / (2 * step), rel=2e-5, abs=2e-5)
    assert np.sum(initial.volume_gradient * direction) == pytest.approx(
        (plus.volume - minus.volume) / (2 * step), rel=2e-5)
    for iteration in range(1, 13):
        method.step(iteration)
    final = model.evaluate(method.x, gradients=False)
    assert final.objective < initial.objective
    assert final.volume <= 1.01 * model.volume_limit
