"""test_pde_filter.py — the PDE (Helmholtz) filter and the volume-preserving Heaviside.

The PDE filter must keep a constant field, conserve volume, behave like the
density filter at the same rmin, and be exactly self-adjoint.  The
volume-preserving Heaviside must keep the mean density to 1e-6 and have a
gradient that includes how its threshold moves.
"""

import numpy as np

from toporia.checks import conformance
from toporia.engine.loop import initialized_method
from toporia.framework.parts.method import OBJECTIVE
from toporia.framework.problem.mesh import make_problem
from toporia.plugins.filters.density import DensityFilter
from toporia.plugins.filters.heaviside import HeavisideFilter
from toporia.plugins.filters.pde import PdeFilter
from toporia.plugins.problems import get_run


def _problem(run):
    return make_problem(run.scenario, run.solver.m)


def _set_up(filt, run):
    filt.setup(_problem(run), run.solver)
    return filt


def _mbb(**values):
    return get_run("MBB Beam").updated(**{"save_every": 0, "m": 0.4, **values})


def test_the_pde_filter_passes_its_conformance_check():
    conformance(PdeFilter).assert_ok()


def test_the_volume_preserving_heaviside_passes_its_adjoint_check():
    class Preserving(HeavisideFilter):
        name = "heaviside_vp_test"
        params = HeavisideFilter.params

        def __init__(self, **kw):
            super().__init__(**{**kw, "eta_mode": "volume_preserving"})

    conformance(Preserving).assert_ok()


def test_a_constant_field_passes_through_the_pde_filter_unchanged():
    run = _mbb()
    filt = _set_up(PdeFilter(rmin=3.0), run)
    field = np.full(_problem(run).shape, 0.37)
    assert np.allclose(filt.forward(field), 0.37, atol=1e-12)


def test_the_pde_filter_conserves_volume_and_is_self_adjoint():
    run = _mbb()
    filt = _set_up(PdeFilter(rmin=2.5), run)
    rng = np.random.default_rng(1)
    shape = _problem(run).shape
    x, y = rng.uniform(size=shape), rng.uniform(size=shape)
    assert abs(filt.forward(x).sum() - x.sum()) < 1e-9 * x.sum()
    assert abs(np.sum(filt.forward(x) * y) - np.sum(x * filt.backward(x, y))) < 1e-9


def test_the_pde_filter_is_in_3d_too():
    run = get_run("Cantilever 3D").updated(save_every=0)
    filt = _set_up(PdeFilter(rmin=1.5), run)
    problem = _problem(run)
    assert problem.dims == 3
    field = np.random.default_rng(2).uniform(size=problem.shape)
    out = filt.forward(field)
    assert out.shape == field.shape and abs(out.sum() - field.sum()) < 1e-9 * field.sum()


def test_the_pde_filter_smooths_like_the_density_filter():
    run = _mbb()
    problem = _problem(run)
    pde, dens = _set_up(PdeFilter(rmin=3.0), run), _set_up(DensityFilter(rmin=3.0), run)
    spike = np.zeros(problem.shape)
    spike[problem.shape[0] // 2, problem.shape[1] // 2] = 1.0
    a, b = pde.forward(spike), dens.forward(spike)
    # Both spread the spike to a neighbourhood of similar size, conserving its volume.
    assert abs(a.sum() - 1.0) < 1e-9
    assert 0.5 < np.sqrt(np.sum(a * np.arange(a.shape[1]) ** 2) / a.sum()
                         - (np.sum(a * np.arange(a.shape[1])) / a.sum()) ** 2) / \
        np.sqrt(np.sum(b * np.arange(b.shape[1]) ** 2) / b.sum()
                - (np.sum(b * np.arange(b.shape[1])) / b.sum()) ** 2) < 2.0


def test_mbb_compliance_with_pde_filter_is_close_to_the_density_filter():
    compliance = {}
    for name in ("density", "pde"):
        run = _mbb(method="q4+oc", max_iter=40, tol=0.0, filter_specs=[{"type": name, "rmin": 3.0}])
        method = initialized_method(run)
        for iteration in range(1, 41):
            method.step(iteration)
        compliance[name] = float(method.get_responses()[OBJECTIVE])
        method.close()
    print("compliance (q4+oc, MBB, rmin 3, 40 it):", compliance)
    assert abs(compliance["pde"] - compliance["density"]) / compliance["density"] < 0.25


def test_volume_preserving_heaviside_keeps_the_mean_density():
    rng = np.random.default_rng(3)
    for beta in (1.0, 4.0, 32.0):
        filt = HeavisideFilter(beta=beta, eta_mode="volume_preserving")
        x = rng.uniform(0.0, 1.0, (8, 24))
        assert abs(filt.forward(x).mean() - x.mean()) < 1e-6


def test_the_default_heaviside_is_unchanged_by_the_new_option():
    x = np.random.default_rng(4).uniform(size=(5, 7))
    a = HeavisideFilter(beta=4.0).forward(x)
    b = (np.tanh(2.0) + np.tanh(4.0 * (x - 0.5))) / (np.tanh(2.0) + np.tanh(2.0))
    assert np.array_equal(a, b) and HeavisideFilter().eta_mode == "fixed"
