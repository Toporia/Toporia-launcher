"""FPTO projection, feasibility, internal continuation and the OC benchmark."""

from types import SimpleNamespace

import numpy as np
import pytest

from toporia.checks.common import iterate
from toporia.checks.updater import check_updater
from toporia.engine.loop import initialized_method
from toporia.plugins.problems import get_run
from toporia.plugins.updaters.floating_projection import FloatingProjectionUpdater
from toporia.plugins.updaters.oc import OCUpdater


class _VolumeModel:
    volume_limit = 0.5

    def __init__(self, lower, upper, weights=None):
        self.lower, self.upper = lower, upper
        self.weights = np.ones_like(lower) if weights is None else weights

    def bounds(self):
        return self.lower.copy(), self.upper.copy()

    def volume_of(self, x):
        return np.sum(self.weights * x) / np.sum(self.weights)


def _updater(model, **settings):
    updater = FloatingProjectionUpdater()
    updater.initialize(model, {"move": 0.2, "fp_beta_max": 8.0, "fp_stage_tol": 0.001, **settings})
    return updater


def test_fpto_passes_the_unchanged_oc_benchmark():
    report = check_updater(FloatingProjectionUpdater)
    assert report.ok, str(report)


@pytest.mark.parametrize("shape", [(5, 7), (3, 4, 5)])
def test_floating_projection_preserves_mass_and_pinned_values_in_2d_and_3d(shape):
    lower, upper = np.zeros(shape), np.ones(shape)
    lower.flat[0] = upper.flat[0] = 1
    upper.flat[-1] = 0
    updater = _updater(_VolumeModel(lower, upper))
    x = np.random.default_rng(9).uniform(0.01, 0.99, shape)
    x = np.clip(x, lower, upper)
    gray = []
    for beta in (1.0, 8.0, 32.0):
        updater.beta = beta
        projected = updater._project(x)
        assert projected.sum() == pytest.approx(x.sum(), abs=1e-10)
        assert projected.flat[0] == 1 and projected.flat[-1] == 0
        assert np.all((projected >= 0) & (projected <= 1))
        gray.append(np.mean(4 * projected * (1 - projected)))
    assert gray[2] < gray[1] < gray[0]


def test_update_measures_weighted_volume_after_projection_move_and_pin_clipping():
    lower, upper = np.zeros((4, 5)), np.ones((4, 5))
    lower.flat[0] = 1
    upper.flat[-1] = 0
    weights = np.linspace(1, 2, 20).reshape(4, 5)
    model = _VolumeModel(lower, upper, weights)
    updater = _updater(model)
    updater.beta = 8
    x = np.clip(np.full(lower.shape, 0.5), lower, upper)
    evaluation = SimpleNamespace(objective_gradient=-np.arange(1, 21).reshape(4, 5).astype(float),
                                 volume_gradient=weights / weights.sum())
    result = updater.update(x, evaluation, 0)
    assert model.volume_of(result) <= model.volume_limit + 1e-10
    assert model.volume_of(result) == pytest.approx(model.volume_limit, abs=1e-7)
    assert np.all(result >= lower) and np.all(result <= upper)
    assert np.max(np.abs(result - x)) <= 0.2 + 1e-15
    assert result.flat[0] == 1 and result.flat[-1] == 0


def test_an_infeasible_start_is_restored_without_breaking_the_move_limit():
    model = _VolumeModel(np.zeros(4), np.ones(4))
    updater = _updater(model)
    evaluation = SimpleNamespace(objective_gradient=-np.ones(4), volume_gradient=np.full(4, 0.25))
    x = np.full(4, 0.9)
    first = updater.update(x, evaluation, 0)
    np.testing.assert_allclose(first, 0.7)
    second = updater.update(first, evaluation, 1)
    assert model.volume_of(second) == pytest.approx(0.5, abs=1e-9)


def test_converged_soft_stages_do_not_stop_the_engine_or_its_check_loop():
    model = _VolumeModel(np.zeros(4), np.ones(4))
    updater = _updater(model, fp_beta_max=2)
    evaluation = SimpleNamespace(objective_gradient=-np.ones(4), volume_gradient=np.full(4, 0.25))
    x = np.full(4, 0.5)
    for completed in range(2):
        x = updater.update(x, evaluation, completed)
        assert updater.continuing()
    assert updater.beta == 2
    updater.update(x, evaluation, 2)
    assert not updater.continuing()  # final stage actually evaluated, not merely scheduled
    assert updater.report()["finished"]
    assert "used beta 2" in updater.report()["message"]
    assert not OCUpdater().continuing()

    class _SettledMethod:
        count = 0

        def step(self, iteration):
            self.count += 1

        def continuing(self):
            return self.count < 3

        def get_change(self):
            return 0

        def is_converged(self):
            return True

    method = _SettledMethod()
    iterate(method, 10, tol=0.01)
    assert method.count == 3


def test_composed_method_propagates_updater_continuation_and_reaches_a_crisp_design():
    run = get_run("MBB Beam").updated(m=0.4, method="q4+floating_projection", max_iter=200, tol=0.01)
    method = initialized_method(run)
    assert method.continuing()
    iterate(method, 200, tol=0.01)
    assert not method.continuing()
    assert method.report()["beta"] == 8
    assert np.mean(4 * method.x * (1 - method.x)) < 0.02
    assert method.get_density().mean() <= run.scenario.volfrac + 1e-8


@pytest.mark.parametrize("settings", [{"move": 0}, {"fp_beta_max": 0},
                                     {"fp_stage_tol": 0}, {"fp_beta_max": np.nan}])
def test_invalid_controls_are_rejected(settings):
    with pytest.raises(ValueError):
        _updater(_VolumeModel(np.zeros(4), np.ones(4)), **settings)
