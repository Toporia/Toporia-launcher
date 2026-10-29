"""Independent geometric fixtures and complete physical-density adjoints."""

import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest

from toporia.framework.params import resolve_params
from toporia.plugins.responses.minimum_length import MinimumLength, calibration, cone_kernel


def response(shape=(12, 16), spacing=None, **settings):
    spacing = spacing or (1.0,)*len(shape)
    problem = SimpleNamespace(shape=shape, dx=spacing[-1], dy=spacing[-2],
                              dz=spacing[0] if len(shape) == 3 else 0)
    part = MinimumLength()
    part.setup(None, problem, resolve_params(part.name, part.params, {"min_length": 6, **settings}))
    return part


@pytest.mark.parametrize("shape,spacing", [((5, 7), (0.7, 1.2)), ((3, 4, 5), (1.1, 0.7, 1.2))])
def test_filter_is_the_independent_truncated_physical_cone_and_has_exact_transpose(shape, spacing):
    part = response(shape, spacing)
    rng = np.random.default_rng(81)
    rho, adjoint = rng.random(shape), rng.normal(size=shape)
    expected = np.zeros(shape)
    for i in np.ndindex(shape):
        denominator = 0.0
        for j in np.ndindex(shape):
            distance = np.sqrt(sum(((a-b)*h)**2 for a, b, h in zip(i, j, spacing, strict=True)))
            weight = max(part.radius-distance, 0)
            expected[i] += weight*rho[j]
            denominator += weight
        expected[i] /= denominator
    np.testing.assert_allclose(part._filter(rho), expected, atol=1e-14)
    assert np.sum(part._filter(rho)*adjoint) == pytest.approx(np.sum(rho*part._filter_adjoint(adjoint)), abs=1e-13)
    np.testing.assert_allclose(part._filter(np.ones(shape)), 1, atol=1e-14)


@pytest.mark.parametrize("phase", ["solid", "void"])
@pytest.mark.parametrize("shape,spacing", [((4, 6), (0.8, 1.2)), ((3, 4, 5), (1.1, 0.8, 1.2))])
def test_complete_gradient_includes_indicator_filter_and_boundary_differences(phase, shape, spacing):
    part = response(shape, spacing, phase=phase)
    rho = np.random.default_rng(17).uniform(0.15, 0.85, shape)
    _, gradient, _ = part.measure(rho)
    fd = np.zeros(shape)
    for index in np.ndindex(shape):
        plus, minus = rho.copy(), rho.copy()
        plus[index] += 1e-6
        minus[index] -= 1e-6
        fd[index] = (part.measure(plus, False)[0]-part.measure(minus, False)[0])/2e-6
    np.testing.assert_allclose(gradient, fd, rtol=1e-6, atol=2e-7)


@pytest.mark.parametrize("shape", [(10, 12), (6, 8, 10)])
def test_phase_complement_and_physical_unit_invariance(shape):
    solid = response(shape)
    void = response(shape, phase="void")
    scaled = response(shape, (3.0,)*len(shape), min_length=18)
    rho = np.random.default_rng(6).random(shape)
    a, da, q = solid.measure(rho)
    b, db, qb = void.measure(1-rho)
    assert a == pytest.approx(b, rel=1e-13)
    np.testing.assert_allclose(da, -db, atol=1e-11)
    np.testing.assert_allclose(q, qb, atol=1e-15)
    c, dc, _ = scaled.measure(rho)
    assert a == pytest.approx(c, rel=1e-13)
    np.testing.assert_allclose(da, dc, atol=1e-11)


@pytest.mark.parametrize("shape", [(12, 16), (5, 8, 10)])
def test_ks_is_a_conservative_peak_constraint_with_bounded_gap(shape):
    part = response(shape)
    rho = np.random.default_rng(14).random(shape)
    aggregate, _, q = part.measure(rho)
    peak = q.max()/part.reference_tolerance
    assert peak-1e-12 <= aggregate <= peak+1/part.settings["sharpness"]+1e-12
    for rho in (np.zeros(shape), np.ones(shape)):
        assert part.measure(rho)[0]-1 < 0


@pytest.mark.parametrize("phase", ["solid", "void"])
def test_resolved_straight_bars_or_channels_distinguish_thin_and_wide_features(phase):
    part = response((40, 50), phase=phase, min_length=10)
    for width, feasible in ((4, False), (8, False), (12, True)):
        rho = np.zeros(part.shape)
        rho[:, 25-width//2:25+(width+1)//2] = 1
        if phase == "void":
            rho = 1-rho
        assert (part.measure(rho)[0] <= 1) == feasible


@pytest.mark.parametrize("phase", ["solid", "void"])
def test_three_dimensional_plate_or_slot_is_controlled(phase):
    part = response((24, 20, 20), phase=phase, min_length=10)
    for width, feasible in ((4, False), (12, True)):
        rho = np.zeros(part.shape)
        rho[12-width//2:12+width//2, :, :] = 1
        if phase == "void":
            rho = 1-rho
        assert (part.measure(rho)[0] <= 1) == feasible


@pytest.mark.parametrize("threshold", [0.6, 0.75, 0.9])
def test_a_bar_exactly_the_requested_length_wide_sits_at_the_threshold(threshold):
    # Independent of the response's quadrature: a fine sampled 2-D cone of radius 1.
    radius_per_length, tolerance = calibration(threshold, 2)
    g = np.linspace(-1, 1, 2001)
    y, x = np.meshgrid(g, g, indexing="ij")
    weight = np.maximum(1-np.hypot(x, y), 0)
    def centre_value(width):     # cone average on the centre line of a bar `width` lengths wide
        return weight[np.abs(y) < width/2/radius_per_length].sum()/weight.sum()
    assert centre_value(1.0) == pytest.approx(threshold, abs=2e-3)
    assert threshold-np.sqrt(tolerance) == pytest.approx(centre_value(0.9), abs=2e-3)


def test_junctions_of_a_truss_with_wide_members_are_not_flagged():
    # Penalising every average below 1 flagged the inside corners of junctions.
    part = response((40, 120), (0.5, 0.5), min_length=6)
    y, x = (np.mgrid[0:40, 0:120]+0.5)*0.5
    for phase, member, feasible in (("solid", 6, True), ("solid", 3, False), ("solid", 1, False)):
        rho = ((y < member) | (y > 20-member)).astype(float)
        for x0 in (0, 30, 60):
            rho[np.abs(x-x0-y)/np.sqrt(2) < member/2] = 1
            rho[np.abs(x-x0+y-20)/np.sqrt(2) < member/2] = 1
        part.settings["phase"] = phase
        assert (part.measure(rho, False)[0] <= 1) == feasible, member


def test_constraint_reporting_and_tolerance_continuation():
    part = response()
    rho = np.full(part.shape, 0.4)
    state = SimpleNamespace(density=rho)
    first = part.evaluate(state)
    assert first.exact is None  # A proxy, not a geometric certificate.
    assert first.reported["length_scale_peak_ratio"] <= first.value+1
    part.settings["limit"] = 2
    second = part.evaluate(state)
    assert second.value < first.value
    assert second.reported["length_scale_tolerance"] == 2*first.reported["length_scale_tolerance"]


def test_insufficient_radius_resolution_is_rejected_instead_of_silent_coarsening():
    with pytest.raises(ValueError, match="at least two cells"):
        cone_kernel(2.0, (1.0, 1.1), (8, 10))


@pytest.mark.skipif(importlib.util.find_spec("nlopt") is None, reason="optional NLopt dependency")
def test_feasible_seeded_optimisation_improves_compliance_and_preserves_both_phase_constraints():
    from experiments.minimum_length import seeded_validation

    initial, density, report = seeded_validation()
    assert density.shape == initial.shape == (16, 24)
    assert report["compliance"] < 0.99*report["initial_compliance"]
    assert report["feasible"], report
    assert max(report["solid_void_residuals"]) <= 1e-6
