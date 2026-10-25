"""Conservation, monotonicity, directional smoothing and Helmholtz solutions."""

from types import SimpleNamespace

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.plugins.filters.pde_anisotropic import AnisotropicPdeFilter


def _filter(shape, **radii):
    filt = AnisotropicPdeFilter(**radii)
    filt.setup(SimpleNamespace(shape=shape), None)
    return filt


def test_conformance_includes_the_finite_difference_adjoint_and_a_pipeline_run():
    conformance(AnisotropicPdeFilter).assert_ok()


@pytest.mark.parametrize("shape", [(7, 19), (4, 7, 9), (1, 8), (1, 1, 1)])
def test_constants_volume_and_the_adjoint_are_preserved(shape):
    filt = _filter(shape, rmin_x=8.0, rmin_y=0.25, rmin_z=3.0)
    rng = np.random.default_rng(3)
    x, seed = rng.uniform(size=shape), rng.normal(size=shape)
    assert filt.forward(np.full(shape, 0.37)) == pytest.approx(np.full(shape, 0.37), abs=1e-12)
    assert filt.forward(x).sum() == pytest.approx(x.sum(), rel=1e-12)
    assert np.sum(filt.forward(x) * seed) == pytest.approx(np.sum(x * filt.backward(x, seed)), abs=1e-12)


@pytest.mark.parametrize("radii", [(0, 0, 0), (12, 0.1, 5), (0.05, 20, 0), (3, 3, 3)])
def test_binary_fields_remain_bounded_for_strong_anisotropy(radii):
    shape = (5, 9, 11)
    filt = _filter(shape, **dict(zip(("rmin_x", "rmin_y", "rmin_z"), radii, strict=True)))
    x = np.random.default_rng(4).integers(0, 2, size=shape).astype(float)
    result = filt.forward(x)
    assert np.min(result) >= -1e-12 and np.max(result) <= 1 + 1e-12
    assert result.sum() == pytest.approx(x.sum(), rel=1e-12)
    if radii == (0, 0, 0):
        assert np.array_equal(result, x)


def test_zero_radius_leaves_variation_along_that_axis_unchanged():
    x = np.broadcast_to(np.arange(9)[:, None] % 2, (9, 17)).astype(float)
    filt = _filter(x.shape, rmin_x=5, rmin_y=0)
    assert filt.forward(x) == pytest.approx(x, abs=1e-12)


def test_a_point_spreads_by_the_prescribed_directional_second_moments():
    shape = (21, 61)
    field = np.zeros(shape)
    field[10, 30] = 1.0
    result = _filter(shape, rmin_x=3.0, rmin_y=1.0).forward(field)
    y, x = np.indices(shape)
    # On an unbounded unit grid, the Helmholtz Green function has variance 2r²
    # in each direction. This domain is wide enough that boundary effects vanish.
    assert np.sum(result * (x - 30) ** 2) == pytest.approx(3.0 ** 2 / 6.0, rel=1e-6)
    assert np.sum(result * (y - 10) ** 2) == pytest.approx(1.0 ** 2 / 6.0, rel=1e-6)


def test_three_dimensional_cosine_has_the_analytic_discrete_helmholtz_gain():
    shape = (4, 7, 9)
    modes = (1, 2, 3)
    radii = (1.0, 2.0, 3.0)  # z, y, x
    phase = np.ones(shape)
    denominator = 1.0
    for axis, (n, mode, radius) in enumerate(zip(shape, modes, radii, strict=True)):
        values = np.cos(mode * np.pi * (np.arange(n) + 0.5) / n)
        broadcast = [1] * 3
        broadcast[axis] = n
        phase *= values.reshape(broadcast)
        denominator += radius ** 2 / 12.0 * 4 * np.sin(mode * np.pi / (2 * n)) ** 2
    field = 0.5 + 0.25 * phase
    result = _filter(shape, rmin_x=3, rmin_y=2, rmin_z=1).forward(field)
    assert result == pytest.approx(0.5 + 0.25 * phase / denominator, abs=1e-12)


def test_mesh_refinement_converges_to_the_continuum_neumann_solution():
    length_scale = 0.1
    exact_gain = 1 / (1 + length_scale ** 2 * np.pi ** 2)
    errors = []
    for n in (16, 32, 64):
        phase = np.cos(np.pi * (np.arange(n) + 0.5) / n)[None, :]
        radius = 2 * np.sqrt(3) * length_scale * n
        result = _filter((1, n), rmin_x=radius, rmin_y=0).forward(phase)
        errors.append(float(np.max(np.abs(result - exact_gain * phase))))
    assert errors[1] < errors[0] / 3.9
    assert errors[2] < errors[1] / 3.9
    assert errors[2] < 1e-4


@pytest.mark.parametrize("radius", [-1, np.nan, np.inf])
def test_invalid_radii_fail_before_factorisation(radius):
    with pytest.raises(ValueError, match="finite and non-negative"):
        AnisotropicPdeFilter(rmin_x=radius)
