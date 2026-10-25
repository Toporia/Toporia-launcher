"""The unregistered SA experiment has a hard solve cap and uses no gradients."""

from types import SimpleNamespace

import numpy as np
import pytest

from experiments.simulated_annealing import anneal
from toporia.plugins.updaters import UPDATERS


class _Model:
    volume_limit = 5.0
    calls = 0

    def bounds(self):
        lower, upper = np.zeros(10), np.ones(10)
        lower[0] = upper[0] = 1
        lower[-1] = upper[-1] = 0
        return lower, upper

    def volume_of(self, x):
        return np.sum(x)

    def initial_design(self):
        return np.full(10, 0.5)

    def evaluate(self, x, gradients=True):
        assert not gradients
        self.calls += 1
        return SimpleNamespace(objective=1 + np.sum((x - np.linspace(0, 1, 10)) ** 2))


def test_budget_feasibility_best_history_and_reproducible_seed():
    first, second = _Model(), _Model()
    a, b = anneal(first, budget=30, seed=4), anneal(second, budget=30, seed=4)
    assert a.evaluations == first.calls == 30
    assert b.evaluations == second.calls == 30
    assert np.array_equal(a.design, b.design)
    assert a.history == b.history
    assert np.all(np.diff(a.history) <= 0)
    assert a.objective == a.history[-1]
    lower, upper = first.bounds()
    assert np.all(a.design >= lower) and np.all(a.design <= upper)
    assert first.volume_of(a.design) <= first.volume_limit + 1e-10
    assert a.design[0] == 1 and a.design[-1] == 0


def test_one_evaluation_budget_only_evaluates_the_start():
    model = _Model()
    result = anneal(model, budget=1)
    assert result.evaluations == model.calls == 1
    assert result.accepted == 0


@pytest.mark.parametrize("kwargs", [{"budget": 0}, {"budget": 1.5}, {"step": 0},
                                   {"temperature": np.nan}, {"final_temperature": -1}])
def test_invalid_controls_are_rejected(kwargs):
    with pytest.raises(ValueError):
        anneal(_Model(), **kwargs)


def test_failed_experiment_is_not_a_selectable_updater():
    assert "simulated_annealing" not in UPDATERS.names()
    assert "annealing" not in UPDATERS.names()
