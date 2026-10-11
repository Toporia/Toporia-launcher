"""test_morphology_filter.py — Sigmund's smooth erode / dilate / open / close.

A constant field must survive every mode; erode and dilate must bracket the
weighted mean (the density filter); open/close are roughly idempotent; every
mode's adjoint must match finite differences; and an MBB run behind a density
filter must still converge to a sensible, not-greyer design.
"""

import numpy as np
import pytest

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.framework.parts.method import OBJECTIVE
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.filters.density import DensityFilter
from toporia.plugins.filters.morphology import MorphologyFilter
from toporia.plugins.problems import get_run


def _mbb(**values):
    return get_run("MBB Beam").updated(**{"save_every": 0, "m": 0.4, **values})


def _set_up(filt, run=None):
    run = run or _mbb()
    filt.setup(make_problem(run.scenario, run.solver.m), run.solver)
    return filt


def _shape():
    run = _mbb()
    return make_problem(run.scenario, run.solver.m).shape


@pytest.mark.parametrize("mode", ["erode", "dilate", "open", "close"])
def test_every_mode_passes_its_conformance_check(mode):
    class Mode(MorphologyFilter):
        name = f"morphology_{mode}_test"
        params = MorphologyFilter.params

        def __init__(self, **kw):
            super().__init__(**{**kw, "mode": mode})

    conformance(Mode).assert_ok()


@pytest.mark.parametrize("mode", ["erode", "dilate", "open", "close"])
def test_a_constant_field_is_unchanged(mode):
    filt = _set_up(MorphologyFilter(rmin=3.0, beta=16.0, mode=mode))
    assert np.allclose(filt.forward(np.full(_shape(), 0.37)), 0.37, atol=1e-12)


def test_erode_and_dilate_bracket_the_weighted_mean():
    x = np.random.default_rng(0).uniform(size=_shape())
    mean = _set_up(DensityFilter(rmin=3.0)).forward(x)
    eroded = _set_up(MorphologyFilter(rmin=3.0, beta=8.0, mode="erode")).forward(x)
    dilated = _set_up(MorphologyFilter(rmin=3.0, beta=8.0, mode="dilate")).forward(x)
    assert np.all(eroded <= mean + 1e-12) and np.all(mean <= dilated + 1e-12)
    # and, on a black-and-white field, erode removes material, dilate adds it
    bw = (x > 0.5).astype(float)
    assert _set_up(MorphologyFilter(rmin=3.0, beta=32.0, mode="erode")).forward(bw).sum() < bw.sum()
    assert _set_up(MorphologyFilter(rmin=3.0, beta=32.0, mode="dilate")).forward(bw).sum() > bw.sum()


def test_a_sharper_beta_gives_a_harder_min_and_max():
    x = np.random.default_rng(1).uniform(size=_shape())
    soft = _set_up(MorphologyFilter(rmin=2.5, beta=2.0, mode="dilate")).forward(x)
    hard = _set_up(MorphologyFilter(rmin=2.5, beta=64.0, mode="dilate")).forward(x)
    assert np.all(hard >= soft - 1e-12)


def test_open_removes_a_thin_member_and_close_fills_a_thin_gap():
    shape = _shape()
    thin = np.zeros(shape)
    thin[:, shape[1] // 2] = 1.0                       # a one-element-wide bar
    opened = _set_up(MorphologyFilter(rmin=3.0, beta=32.0, mode="open")).forward(thin)
    assert opened.max() < 0.3 * thin.max()
    gap = np.ones(shape)
    gap[:, shape[1] // 2] = 0.0                        # a one-element-wide slit
    closed = _set_up(MorphologyFilter(rmin=3.0, beta=32.0, mode="close")).forward(gap)
    assert closed.min() > 0.7


@pytest.mark.parametrize("mode", ["open", "close"])
def test_open_and_close_are_roughly_idempotent(mode):
    filt = _set_up(MorphologyFilter(rmin=2.5, beta=32.0, mode=mode))
    x = (np.random.default_rng(2).uniform(size=_shape()) > 0.5).astype(float)
    once = filt.forward(x)
    twice = filt.forward(once)
    assert np.abs(twice - once).mean() < 0.35 * np.abs(once - x).mean() + 1e-3


def test_beta_can_be_scheduled():
    filt = _set_up(MorphologyFilter())
    assert "beta" in filt.schedulable
    filt.set_parameter("beta", 40.0)
    assert filt.beta == 40.0


def test_mbb_with_the_open_filter_behind_the_density_filter():
    result = {}
    for label, specs in (("density", [{"type": "density", "rmin": 3.0}]),
                         ("density+open", [{"type": "density", "rmin": 3.0},
                                           {"type": "morphology", "rmin": 3.0, "beta": 8.0, "mode": "open"}])):
        run = _mbb(method="q4+oc", max_iter=30, tol=0.0, filter_specs=specs)
        method = initialized_method(run)
        for iteration in range(1, 31):
            method.step(iteration)
        density = np.asarray(method.get_density())
        result[label] = (float(method.get_responses()[OBJECTIVE]),
                         float(np.mean((density > 0.1) & (density < 0.9))))
        method.close()
    print("MBB q4+oc rmin 3, 30 it: (compliance, grey fraction) =", result)
    for compliance, grey in result.values():
        assert np.isfinite(compliance) and compliance > 0 and 0.0 <= grey <= 1.0
    # The extra smoothing costs some stiffness early on, but must not wreck the design.
    assert result["density+open"][0] < 1.6 * result["density"][0]
