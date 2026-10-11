"""test_manufacturing_filters.py - extrusion, pattern repetition and casting.

Each filter is a structural property of its output (constant along an axis,
periodic, monotone along the draw direction), checked on a random field in 2-D
and 3-D, plus a short optimisation run with each.  The gradient is checked by
`toporia check filter:<name>`.
"""

import numpy as np
import pytest

from toporia.engine.loop import initialized_method
from toporia.plugins.filters.casting import CastingFilter
from toporia.plugins.filters.extrusion import ExtrusionFilter
from toporia.plugins.filters.pattern import PatternFilter
from toporia.plugins.problems import get_run


class _P2:
    dims = 2
    shape = (6, 12)


class _P3:
    dims = 3
    shape = (4, 6, 12)


class _Odd:
    dims = 2
    shape = (6, 13)


def _field(problem, seed=0):
    return np.random.default_rng(seed).uniform(0.0, 1.0, problem.shape)


@pytest.mark.parametrize("problem, axis", [(_P2, "x"), (_P2, "y"), (_P3, "x"), (_P3, "y"), (_P3, "z")])
def test_extrusion_is_constant_along_its_axis(problem, axis):
    filt = ExtrusionFilter(axis=axis)
    filt.setup(problem, None)
    x = _field(problem)
    y = filt.forward(x)
    ax = {"x": -1, "y": -2, "z": 0}[axis]
    assert np.ptp(y, axis=ax).max() < 1e-12
    assert y.mean() == pytest.approx(x.mean())          # the mean is conserved


def test_extrusion_along_z_is_refused_in_2d():
    with pytest.raises(ValueError, match="3-D"):
        ExtrusionFilter(axis="z").setup(_P2, None)


@pytest.mark.parametrize("problem, reps", [(_P2, (3, 2, 1)), (_P3, (2, 2, 4))])
def test_pattern_is_periodic(problem, reps):
    nx, ny, nz = reps
    filt = PatternFilter(nx=nx, ny=ny, nz=nz)
    filt.setup(problem, None)
    x = _field(problem)
    y = filt.forward(x)
    counts = (nz, ny, nx)[-len(problem.shape):]
    cell = y[tuple(slice(0, n // r) for n, r in zip(problem.shape, counts, strict=True))]
    assert np.allclose(y, np.tile(cell, counts))
    assert y.mean() == pytest.approx(x.mean())


def test_pattern_refuses_a_count_that_does_not_divide():
    with pytest.raises(ValueError, match="13 elements along x cannot be split into 2"):
        PatternFilter(nx=2).setup(_Odd, None)


@pytest.mark.parametrize("problem, direction", [(_P2, "+x"), (_P2, "-x"), (_P2, "+y"), (_P2, "-y"),
                                                (_P3, "+z"), (_P3, "-z"), (_P3, "+y")])
def test_casting_is_monotone_along_the_draw_direction(problem, direction):
    filt = CastingFilter(direction=direction)
    filt.setup(problem, None)
    y = filt.forward(_field(problem))
    ax = {"x": -1, "y": -2, "z": 0}[direction[1]]
    step = np.diff(np.moveaxis(y, ax, 0), axis=0)
    if direction[0] == "-":
        step = -step
    assert step.max() <= 5e-4 + 1e-12                   # never rises, to the smoothing tolerance
    assert y.min() >= 0 and y.max() <= 1 + 1e-9


def test_casting_leaves_an_already_monotone_design_alone():
    filt = CastingFilter(direction="+y")
    filt.setup(_P2, None)
    x = np.linspace(1.0, 0.0, 6)[:, None] * np.ones((6, 12))
    assert np.allclose(filt.forward(x), x, atol=5e-4)


@pytest.mark.parametrize("spec", [{"type": "extrusion", "axis": "y"}, {"type": "pattern", "nx": 2},
                                  {"type": "casting", "direction": "+y"}])
def test_a_short_mbb_run_with_each(spec):
    run = get_run("MBB Beam").updated(method="q4+oc", m=0.4, max_iter=4, tol=0.0, save_every=0,
                                      filter_specs=[{"type": "density"}, spec])
    method = initialized_method(run)
    for i in range(1, 5):
        method.step(i)
    assert np.all(np.isfinite(method.get_density()))


@pytest.mark.parametrize("spec", [{"type": "extrusion", "axis": "z"}, {"type": "pattern", "nx": 2},
                                  {"type": "casting", "direction": "+z"}])
def test_a_short_cantilever_3d_run_with_each(spec):
    run = get_run("Cantilever 3D").updated(save_every=0, max_iter=3, tol=0.0,
                                           filter_specs=[{"type": "density"}, spec])
    method = initialized_method(run)
    for i in range(1, 4):
        method.step(i)
    assert np.all(np.isfinite(method.get_density()))
